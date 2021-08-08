from enum import Enum
from typing import Match, List, TextIO, Final
from pathlib import Path
import logging
import os
import re
import sys

HEALER_ROSTER = ["Hôsteric", "Delvur", "Yashar", "Pv", "Runnz",
                 "Lífeforce", "Seiton"]

RAID_LEAD = "Slickduck"


class RaidLeadVisibility(Enum):
    ALL = 1
    HEALER_CDS = 2
    NON_HEALER_CDS = 3


PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)))

SOURCE = os.path.join(PATH, 'soulrender-cds.txt')

NON_HEALER_DEST = os.path.join(PATH, 'non-healer-cds.txt')

ENCAPSULATED_CD_DEST = os.path.join(PATH, 'encapsulapted-cds.txt')

HEADER_REGEX: Final = re.compile(r".*-.*?-\s")

RAID_CD_REGEX: Final = re.compile(
    r"\|c[0-9abcdefABCDEF]{6,8}([\s\w]*)\|r(\s*{spell:[0-9]*}\s\s)")


def handle_data_format_bug_1(event_list) -> List[str]:
    """Fix for a known formatting bug.

    Spreadsheet can sometimes export cds where there is no space between
    name and spell id. This function adds that space.
    https://discord.com/channels/756215582021517473/804095740207956009/873297331175432212

    Args:
    event_list(List[str]): source list of events to be fixed.

    Returns:
        List of correctly formatted cds.

    """
    fixed_event_list = []
    for event in event_list:
        event = re.sub('[|]r{', '|r {', event)
        fixed_event_list.append(event)
    return fixed_event_list


def append_event_to_file(event, dest_file):
    """Copies an event to a specified file.

    Args:
        event(str): The entire event to be copied to the specified file.
        An event consists of an event header and list of healer cooldowns.

        dest_file(TextIO): The file that will  be written to.
    """

    dest_file.write(event + '\n')


def clear_file(file_name):
    """Clear the contents of file at the specified path

    Args:
        file_name(str): The path of the file to clear.
    """
    if os.path.isfile(file_name):
        file = open(file_name, 'w')
        file.close()


def find_header(event) -> str:
    """Returns the header portion of an event.

    A header is everything behind the second - including the space after.
    Usually one of the following formats:
    Dynamic Timers: {time:00:00} |c00000000Name|r - 00:00 -
    Static Timers:  |c00000000Name|r - 00:00 -

    Args:
        event(str): The full event string.
    """
    match = HEADER_REGEX.match(event)
    if match is None:
        logging.error("Error parsing header for event event=" + event)
        return " "
    return match.group()


def find_cds_for_healer(event, healer) -> List[Match]:
    """Returns a list of match objects for a given healer

    A cd consists of a name and a spell, in the following format:

      color   name     spell-icon
    |cfff38bb9Runnz|r {spell:31821}

    Given an event, we run use a regex search to find all of cds the
    given healer has this event, and package them into a list of Match
    Objects.

    Match Object:
        Group 1) Name
        Group 2) Spell

    Args:
        event(str): The full event string.
        healer(str): The healer whose cds we're looking for.
    """
    healer_matches = []

    matches = RAID_CD_REGEX.finditer(event)

    for match in matches:
        if match.groups()[0] == healer:
            healer_matches.append(match)
    return healer_matches


def get_healer_cd_text_from_matches(healer_cd_matches) -> str:
    """Returns a concatenated string of all cds give the list of matches

    Args:
        healer_cd_matches(List[Match]): The list of match objects we can use
        to get the cd string from.
    """

    cd_text = ""
    for match in healer_cd_matches:
        cd_text += match[0]

    return cd_text


def do_split_healer_events(event_list, dest_file, healer):
    """Splits healer cds into files according to healer

    Args:
        event_list(List[str]): The full list of damage events.
        dest_file(TextIO): The file we'll be copying events to.
        healer: The current healer that we're copying cds for.
    """
    event_list = handle_data_format_bug_1(event_list)
    for event in event_list:

        # This is the list of cds the current healer has on this boss ability
        healer_cd_matches = find_cds_for_healer(event, healer)

        # This is the concatenated string of cds for this event and healer.
        healer_cd_text = get_healer_cd_text_from_matches(healer_cd_matches)

        if healer_cd_text:
            # This is the boss ability name and timestamp.
            header = find_header(event)

            event_text = header + healer_cd_text
            append_event_to_file(event_text, dest_file)


def split_healer_events(cd_source):
    """Splits healer events into their respective files. """
    for healer in HEALER_ROSTER:
        with open(os.path.join(PATH, healer + '-cds.txt'),
                  'a+', encoding='utf-8') as cd_dest:
            do_split_healer_events(cd_source, cd_dest, healer)


def remove_cds_from_event(event, healer) -> str:
    """Returns an event line that has been stripped of healer cds

    Args:
        event(str): The event we're processing
        healer(str): The healer whose cds are being stripped from the event.
    """
    matches = find_cds_for_healer(event, healer)
    processed_event = event
    for matchNum, match in enumerate(matches, start=1):
        groups = match.groups()
        if groups[0] == healer:
            processed_event = processed_event.replace(match[0], "")
    return processed_event


def do_strip_healer_cds(event_list, dest_file):
    """Strips healer cds from every event

    Non-healer cds all go in the same file. This function will take
    every event and remove all of the healer cds such that all that remains
    is the non-healer cds.

    Args:
        event_list(List[str]): The list of events to process
        dest_file(TextIO): The destination file to copy non-healer cds.
    """
    event_list = handle_data_format_bug_1(event_list)
    for event in event_list:
        header = find_header(event)
        processed_event = event
        processed_event = processed_event.replace(header, "")
        processed_event = processed_event.replace("\n", "")
        for current_healer in HEALER_ROSTER:
            processed_event = remove_cds_from_event(processed_event,
                                                    current_healer)
        if processed_event:
            processed_event = header + processed_event
            append_event_to_file(processed_event, dest_file)


def strip_healer_cds(event_list):
    """Strips healer cds from the event list"""
    with open(NON_HEALER_DEST, 'a+', encoding='utf-8') as dest_file:
        do_strip_healer_cds(event_list, dest_file)


def should_be_visible_to_raid_leader(raider, raid_lead_visibility) -> bool:
    """Returns whether the raid leader should included in visibility

    i.e, your raid leader may still want to call for non-healer cds or even
    healer cds. This function returns true if the raider's status matches
    the value of raid_lead_visibility.

    Args:
        raider: The name of the current raider. Used to look up whether healer
        or not.
        raid_lead_visibility(RaidLeadVisibility): flag that determines
        whether the raid leader should be concerned about the raider's cds.
        ALL - your raid leader will be able to see all raid cds
        HEALER_CDS - your raid leader will be able to see all healer cds
        NON_HEALER_CDS - your raid leader will be able to see cds only from
        non healers like DH, DK, Warrior, etc.
    """

    if raid_lead_visibility == RaidLeadVisibility.ALL:
        return True
    elif (raid_lead_visibility == RaidLeadVisibility.HEALER_CDS and
            raider in HEALER_ROSTER):
        return True
    elif (raid_lead_visibility == RaidLeadVisibility.NON_HEALER_CDS and
            raider not in HEALER_ROSTER):
        return True

    return False


def get_encapsulated_cd_from_match(cd_match, raid_lead_visibility) -> str:
    """Returns the healing cd wrapped in ERT visibility tags

    Positive visibility tags have the following syntax:
         opening tag      text   closing tag
        {p: List[names]} ....... {/p}}
        Any text between the opening and closing tag will only be visible
        to raiders whose names are in the list of names.

    Args:
        cd_match(Match Object): The entire match object for a healing cd.
        raid_lead_visibility(bool): flag that determines whether a the raid
        leader should also be able to see this cd.
    """

    visibility_list = []
    groups = cd_match.groups()
    raider_name = groups[0]

    if should_be_visible_to_raid_leader(raider_name, raid_lead_visibility):
        visibility_list.append(RAID_LEAD)

    visibility_list.append(raider_name)

    visibility_str = ','.join(visibility_list)
    cd = cd_match[0]
    encapsulated_cd = f"{{p:{visibility_str}}}{cd}{{/p}}"
    return encapsulated_cd


def encapsulate_cds(event_list, raid_lead_visibility):
    """Wraps cds in the event list with encapsulators that will cause
    ERT to only render cds to their cooresponding owners. The logic for
    visibility is as follows:

    If noone has cds for an event, the event is not added to the ERT note.
    If a raider has a cd for an event, that event header and cd is visible
        only to that raider
    If the raid leader should also see the raider's cd according to the
        raid_lead_visibility flag, then the event and specific raider cd
        will also be visible to the raid lead.

    ARGS:
        event_list(List(str)): List of events containing raid cds.
        raid_lead_visibility(boolean): indicates whether the raid leader should
        be included in the encapsulation.
    """
    encapsulated_event_text = ""
    for event in event_list:
        header = find_header(event)
        cds = ""
        matches = RAID_CD_REGEX.finditer(event)

        # If a healer has no cds for this event, they should also not see a
        # header.
        header_visibility_list = []
        is_header_visible_to_rl = False
        for match in matches:
            groups = match.groups()
            raider_name = groups[0]
            # If we matched a healer for this event, the header should be
            # visible to them.
            header_visibility_list.append(raider_name)
            is_raider_visible_to_rl = should_be_visible_to_raid_leader(
                raider_name, raid_lead_visibility)

            # If any raider cd in this event is visible to the raid leader,
            # then the raidleader should also see the header.
            is_header_visible_to_rl |= is_raider_visible_to_rl

            cds += get_encapsulated_cd_from_match(match,
                                                  raid_lead_visibility)

        if is_header_visible_to_rl:
            header_visibility_list.append(RAID_LEAD)

        # Only add unique values to the visibility list.
        header_visibility_set = list(set(header_visibility_list))
        visibility_str = ','.join(header_visibility_set)

        # Don't add event if noone has cds on it.
        if cds:
            # Don't show a header to people who don't have cds for this event.
            encapsulated_header = f"{{p:{visibility_str}}}{header}{{/p}}"
            encapsulated_event_text += f"{encapsulated_header}{cds}\n"

    with open(ENCAPSULATED_CD_DEST, 'a+', encoding='utf8') as dest_file:
        append_event_to_file(encapsulated_event_text, dest_file)


def main():
    for healer in HEALER_ROSTER:
        file_name = healer + '-cds.txt'
        clear_file(file_name)

    clear_file(NON_HEALER_DEST)
    with open(SOURCE, 'r', encoding='utf-8') as test_file:
        event_list = test_file.readlines()
        split_healer_events(event_list)
        strip_healer_cds(event_list)

    raid_lead_visibility = RaidLeadVisibility.NON_HEALER_CDS
    clear_file(ENCAPSULATED_CD_DEST)
    with open(SOURCE, 'r', encoding='utf-8') as source_file:
        event_list = source_file.readlines()
        encapsulate_cds(event_list, raid_lead_visibility)


if __name__ == "__main__":
    main()
