import re

from django import template

register = template.Library()


@register.filter(name="truncate_middle")
def truncate_middle(value, arg):
    if len(value) > arg:
        half_arg = arg // 2
        return value[:half_arg] + "..." + value[-half_arg:]
    return value


@register.filter(name="truncate_folder_name")
def truncate_folder_name(value, length):
    if len(value) <= length:
        return value
    else:
        first_part = value[: length // 2]
        second_part = value[-(length // 2) :]
        return first_part + "..." + second_part


@register.filter(name="truncate_legend")
def truncate_legend(value, max_length):
    if len(value) > max_length:
        return value[: max_length // 2] + "..." + value[-max_length // 2 :]
    return value


@register.filter(name="extract_filename")
def extract_filename(value):
    pattern = re.compile(r'^\d{8}_\d{6}_\d{6}___')

    if pattern.match(value):
        parts = value.split('_')

        # Extract the desired portions when the pattern matches
        new_filename = value[:8] + '_' + '_'.join(parts[6:])
        return new_filename

    elif len(value) > 20:
        # Truncate the name and insert ellipsis in the middle if the length exceeds 30 characters
        half_length = len(value) // 2
        new_filename = value[:half_length - 3] + '...' + value[half_length + 3:]
        return new_filename

    return value  # Return the original value if it doesn't meet the conditions