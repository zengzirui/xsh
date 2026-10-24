from .XsError import XsError
class CommandError(XsError):
    pass
class CommandArgsError(CommandError):
    pass
