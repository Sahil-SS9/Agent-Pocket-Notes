"""Keep the already-open widget path cheap: no store, argparse, research or Tk."""
import sys

def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    fast_args = list(args[1:]) if args and args[0]=='widget' else []
    if '--renderer' in fast_args:
        i=fast_args.index('--renderer')
        if i+1<len(fast_args) and fast_args[i+1] in {'auto','qt','tk'}: del fast_args[i:i+2]
    if not args or (args[0]=='widget' and set(fast_args)<={'--background','--if-not-running'}):
        from .locations import default_home
        from .wake import raise_existing
        if raise_existing(default_home()):
            return 0
    from .cli import main as dispatch
    return dispatch(args)
