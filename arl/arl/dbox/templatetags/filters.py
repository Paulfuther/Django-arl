from django import template

register = template.Library()

@register.filter(name='truncate_middle')
def truncate_middle(value, arg):
    if len(value) > arg:
        half_arg = arg // 2
        return value[:half_arg] + '...' + value[-half_arg:]
    return value

@register.filter
def truncate_folder_name(value, length):
    if len(value) <= length:
        return value
    else:
        first_part = value[:length // 2]
        second_part = value[-(length // 2):]
        return first_part + '...' + second_part
    
@register.filter(name='truncate_legend')
def truncate_legend(value, max_length):
    if len(value) > max_length:
        return value[:max_length // 2] + '...' + value[-max_length // 2:]
    return value