def register_commands(app):
    """Register CLI commands with Flask app"""
    from .scheduler import start_scheduler
    app.cli.add_command(start_scheduler)
