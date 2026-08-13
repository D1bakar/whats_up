"""Centralized bot response templates for future localization."""

WELCOME = (
    "Welcome! I'm your WhatsApp assistant.\n\n"
    "Send /help to see available commands or /menu to view options."
)

HELP = (
    "Available commands:\n"
    "• /start — restart the conversation\n"
    "• /help — show this help message\n"
    "• /menu — show the main menu\n\n"
    "You can also type commands without the leading slash."
)

MENU = (
    "Main menu:\n"
    "1. Demo flow — type *demo* to try a sample multi-step flow\n"
    "2. Help — type *help*\n"
    "3. Start over — type *start*"
)

DEFAULT_FALLBACK = (
    "I didn't understand that.\n\nTry /menu to see available options, or /help for commands."
)

UNKNOWN_COMMAND = "Unknown command.\n\nSend /help to see what I can do, or /menu for the main menu."

DEMO_FLOW_START = (
    "Demo flow started.\n\nPlease reply with your name (or type *cancel* to return to the menu)."
)

DEMO_FLOW_COLLECTED = "Thanks, {name}!\n\nReply *yes* to confirm or *no* to start over."

DEMO_FLOW_CONFIRMED = "Demo complete! Returning to the main menu.\n\n{menu}"

DEMO_FLOW_CANCELLED = "Demo cancelled. Returning to the main menu.\n\n{menu}"

DEMO_FLOW_INVALID = "Please reply with your name, or type *cancel* to go back."

DEMO_FLOW_CONFIRM_INVALID = "Please reply *yes* or *no*, or type *cancel*."
