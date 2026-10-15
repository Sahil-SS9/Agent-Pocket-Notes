"""Directory-plugin entry: the sibling package is relative to the plugin root."""
def register(ctx):
    from .sticky_intent.hermes_plugin import register as register_plugin
    register_plugin(ctx)
