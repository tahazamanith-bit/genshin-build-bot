from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
import asyncio
import os
import time
import sqlite3
import logging
from logging.handlers import RotatingFileHandler

from telegram.error import Forbidden, RetryAfter

from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from database import (
    get_all_characters,
    get_characters_by_element,
    get_character,
    get_character_by_name,
    add_character,
    update_character,
    delete_character,
    get_admin,
    get_all_admins,
    get_all_owners,
    get_all_regular_admins,
    add_admin,
    remove_admin,
    MAIN_OWNER_ID,
    create_manual_backup,
    validate_sqlite_backup,
    restore_database_from_file,
    get_all_user_ids,
)


# =========================================================
# PING LOGGING
# =========================================================

PING_LOG_FOLDER = "logs"
os.makedirs(PING_LOG_FOLDER, exist_ok=True)


ping_logger = logging.getLogger("ping")
ping_logger.setLevel(logging.INFO)
ping_logger.propagate = False

if not ping_logger.handlers:
    ping_handler = RotatingFileHandler(
        os.path.join(PING_LOG_FOLDER, "ping.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    ping_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    ping_logger.addHandler(ping_handler)


DATABASE_PATH = "data/bot.db"


# =========================================================
# PERMISSIONS
# =========================================================

def is_owner(user_id):
    admin = get_admin(user_id)
    return admin is not None and admin["role"] == "owner"


def is_admin(user_id):
    admin = get_admin(user_id)
    return admin is not None and admin["role"] in ("owner", "admin")


# =========================================================
# ELEMENTS
# =========================================================

ELEMENTS = {
    "pyro": "🔥 Pyro",
    "hydro": "💧 Hydro",
    "anemo": "🌪️ Anemo",
    "cryo": "❄️ Cryo",
    "electro": "⚡ Electro",
    "dendro": "🌿 Dendro",
    "geo": "🪨 Geo",
}


# =========================================================
# BUILD FIELDS
# =========================================================

FIELDS = [
    ("name", "Character Name"),
    ("weapons", "Recommended Weapons"),
    ("weapons_notes", "Weapon Notes"),
    ("constellation", "Recommended Constellation"),
    ("artifact", "Recommended Artifact"),
    ("artifact_notes", "Artifact Notes"),
    ("main_stats", "Artifact Main Stats"),
    ("sub_stats", "Artifact Sub Stats"),
    ("sub_stats_notes", "Sub Stats Notes"),
    ("stat_goals", "Recommended Stats"),
    ("talents", "Talent Leveling Order"),
    ("teams", "Recommended Teams"),
    ("rotation", "Rotation"),
    ("notes", "Notes"),
    ("c1", "C1"),
    ("c2", "C2"),
    ("c3", "C3"),
    ("c4", "C4"),
    ("c5", "C5"),
    ("c6", "C6"),
]

FIELD_TITLES = dict(FIELDS)


# =========================================================
# COMMON KEYBOARDS
# =========================================================

def build_management_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Character", callback_data="admin_add_character")],
        [InlineKeyboardButton("✏️ Edit Build", callback_data="admin_edit_character")],
        [InlineKeyboardButton("🗑️ Delete Build", callback_data="admin_delete_character")],
        [InlineKeyboardButton("🧩 Elements", callback_data="admin_elements")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
    ])


def add_step_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="add_back"
            ),
            InlineKeyboardButton(
                "Next ▶️",
                callback_data="add_next"
            ),
        ]
    ])


def add_first_step_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="add_back"
            ),
            InlineKeyboardButton(
                "Next ▶️",
                callback_data="add_next"
            ),
        ],
        [
            InlineKeyboardButton(
                "❌ Close",
                callback_data="add_close"
            ),
        ],
    ])


# =========================================================
# ADMIN MAIN
# =========================================================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "❌ You do not have permission."
        )
        return

    keyboard = [
        [
            InlineKeyboardButton("🤖 Bot Management", callback_data="admin_bot_management"),
            InlineKeyboardButton("📚 Build Management", callback_data="admin_build_menu"),
        ],
        [
            InlineKeyboardButton("🗄️ Backup", callback_data="admin_backup"),
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        ],
    ]

    await update.message.reply_text(
        "🛠️ Admin Panel\n\n"
        "Select a section:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_main_callback(update, context):

    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            "❌ You do not have permission."
        )
        return

    keyboard = [
        [
            InlineKeyboardButton("🤖 Bot Management", callback_data="admin_bot_management"),
            InlineKeyboardButton("📚 Build Management", callback_data="admin_build_menu"),
        ],
        [
            InlineKeyboardButton("🗄️ Backup", callback_data="admin_backup"),
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        ],
    ]

    await query.edit_message_text(
        "🛠️ Admin Panel\n\n"
        "Select a section:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_build_menu_callback(update, context):

    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            "❌ You do not have permission."
        )
        return

    await query.edit_message_text(
        "📚 Build Management\n\n"
        "Select an operation:",
        reply_markup=build_management_keyboard()
    )


# =========================================================
# ADD CHARACTER
# =========================================================

(
    ADD_ELEMENT,
    ADD_NAME,
    ADD_WEAPONS,
    ADD_WEAPONS_NOTES,
    ADD_CONSTELLATION,
    ADD_ARTIFACT,
    ADD_ARTIFACT_NOTES,
    ADD_MAIN_STATS,
    ADD_SUB_STATS,
    ADD_SUB_STATS_NOTES,
    ADD_STAT_GOALS,
    ADD_TALENTS,
    ADD_TEAMS,
    ADD_ROTATION,
    ADD_NOTES,
    ADD_C1,
    ADD_C2,
    ADD_C3,
    ADD_C4,
    ADD_C5,
    ADD_C6,
) = range(21)


FIELD_STATES = {
    "name": ADD_NAME,
    "weapons": ADD_WEAPONS,
    "weapons_notes": ADD_WEAPONS_NOTES,
    "constellation": ADD_CONSTELLATION,
    "artifact": ADD_ARTIFACT,
    "artifact_notes": ADD_ARTIFACT_NOTES,
    "main_stats": ADD_MAIN_STATS,
    "sub_stats": ADD_SUB_STATS,
    "sub_stats_notes": ADD_SUB_STATS_NOTES,
    "stat_goals": ADD_STAT_GOALS,
    "talents": ADD_TALENTS,
    "teams": ADD_TEAMS,
    "rotation": ADD_ROTATION,
    "notes": ADD_NOTES,
    "c1": ADD_C1,
    "c2": ADD_C2,
    "c3": ADD_C3,
    "c4": ADD_C4,
    "c5": ADD_C5,
    "c6": ADD_C6,
}


def initialize_new_build(context):

    context.user_data["new_build"] = {
        field: ""
        for field, _ in FIELDS
    }
    context.user_data["new_build"]["element"] = ""


async def show_add_field(update, context, field):

    title = FIELD_TITLES[field]

    current_value = context.user_data.get("new_build", {}).get(field, "")

    if current_value:
        text = (
            f"✏️ {title}\n\n"
            "Current value:\n"
            f"{current_value}\n\n"
            "Send a new value to replace it, or press 'Next ▶️' to keep it."
        )
    else:
        text = (
            f"✏️ {title}\n\n"
            "No value entered yet.\n\n"
            "Send the value for this section, or press 'Next ▶️' to leave it empty."
        )

    if field == "name":
        keyboard = add_first_step_keyboard()
    else:
        keyboard = add_step_keyboard()

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=keyboard
        )


def element_keyboard_for_add():
    buttons = []
    for key, label in ELEMENTS.items():
        buttons.append([InlineKeyboardButton(label, callback_data=f"add_element_{key}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="add_close")])
    return InlineKeyboardMarkup(buttons)


async def add_character_start(update, context):

    if not is_admin(update.effective_user.id):
        await update.callback_query.answer(
            "❌ You do not have permission.",
            show_alert=True
        )
        return ConversationHandler.END

    await update.callback_query.answer()

    initialize_new_build(context)

    await update.callback_query.edit_message_text(
        "➕ Add Character\n\nSelect the character's element first:",
        reply_markup=element_keyboard_for_add()
    )

    return ADD_ELEMENT


async def add_element_selected(update, context):
    query = update.callback_query
    await query.answer()

    element = query.data.replace("add_element_", "")
    if element not in ELEMENTS:
        await query.answer("Invalid element.", show_alert=True)
        return ADD_ELEMENT

    context.user_data["new_build"]["element"] = element
    context.user_data["add_current_field"] = "name"

    await show_add_field(update, context, "name")
    return ADD_NAME


async def add_receive(update, context, field):

    value = update.message.text

    context.user_data["new_build"][field] = value

    context.user_data["add_current_field"] = field

    return await go_next_add_field(
        update,
        context
    )


async def go_next_add_field(update, context):

    current_field = context.user_data.get(
        "add_current_field"
    )

    if current_field not in FIELD_STATES:
        current_field = "name"

    fields = [x[0] for x in FIELDS]

    current_index = fields.index(current_field)

    if current_index >= len(fields) - 1:

        await show_finish_add(
            update,
            context
        )

        return ConversationHandler.END

    next_field = fields[current_index + 1]

    context.user_data["add_current_field"] = next_field

    await show_add_field(
        update,
        context,
        next_field
    )

    return FIELD_STATES[next_field]


async def add_next(update, context):

    query = update.callback_query
    await query.answer()

    current_field = context.user_data.get(
        "add_current_field"
    )

    if current_field not in FIELD_STATES:
        current_field = "name"
        context.user_data["add_current_field"] = "name"

    fields = [x[0] for x in FIELDS]

    current_index = fields.index(current_field)

    if current_index >= len(fields) - 1:

        await show_finish_add(
            update,
            context
        )

        return ConversationHandler.END

    next_field = fields[current_index + 1]

    context.user_data["add_current_field"] = next_field

    await show_add_field(
        update,
        context,
        next_field
    )

    return FIELD_STATES[next_field]


async def add_back(update, context):

    query = update.callback_query
    await query.answer()

    current_field = context.user_data.get(
        "add_current_field",
        "name"
    )

    fields = [x[0] for x in FIELDS]

    current_index = fields.index(current_field)

    if current_index == 0:
        await query.edit_message_text(
            "➕ Add Character\n\nSelect the character's element first:",
            reply_markup=element_keyboard_for_add()
        )
        return ADD_ELEMENT

    previous_field = fields[current_index - 1]

    context.user_data["add_current_field"] = previous_field

    await show_add_field(
        update,
        context,
        previous_field
    )

    return FIELD_STATES[previous_field]


async def add_close(update, context):

    query = update.callback_query
    await query.answer()

    context.user_data.pop(
        "new_build",
        None
    )

    context.user_data.pop(
        "add_current_field",
        None
    )

    await query.edit_message_text(
        "🛠️ Admin Panel\n\n"
        "Select a section:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🤖 Bot Management",
                    callback_data="admin_bot_management"
                )
            ],
            [
                InlineKeyboardButton(
                    "📚 Build Management",
                    callback_data="admin_build_menu"
                )
            ],
        ])
    )

    return ConversationHandler.END


# =========================================================
# FINISH ADD
# =========================================================

def finish_add_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✏️ Edit Sections",
                callback_data="build_edit_sections"
            )
        ],
        [
            InlineKeyboardButton(
                "💾 Save Build",
                callback_data="build_save"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="build_cancel"
            )
        ],
    ])


def preview_build(data):

    lines = [
        "📋 Build Preview",
        ""
    ]

    for field, title in FIELDS:

        value = data.get(field, "")

        if value:
            lines.append(
                f"🔹 {title}:"
            )
            lines.append(value)
            lines.append("")

    if len(lines) <= 2:
        lines.append(
            "No information has been entered yet."
        )

    return "\n".join(lines)


async def show_finish_add(update, context):

    data = context.user_data.get(
        "new_build",
        {}
    )

    keyboard = finish_add_keyboard()

    if update.callback_query:

        await update.callback_query.edit_message_text(
            preview_build(data),
            reply_markup=keyboard
        )

    else:

        await update.message.reply_text(
            preview_build(data),
            reply_markup=keyboard
        )


async def build_save(update, context):

    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            "❌ You do not have permission."
        )
        return ConversationHandler.END

    data = context.user_data.get(
        "new_build"
    )

    if not data:
        await query.edit_message_text(
            "❌ Build data not found."
        )
        return ConversationHandler.END

    name = data.get(
        "name",
        ""
    ).strip()

    if not name:

        await query.answer(
            "❌ Character name is required.",
            show_alert=True
        )

        return ConversationHandler.END

    if get_character_by_name(name):

        await query.answer(
            "❌ This character already exists.",
            show_alert=True
        )

        return ConversationHandler.END

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = update.effective_user
    actor = user.username or user.full_name or str(user.id)
    data["created_by"] = actor
    data["created_at"] = now
    data["updated_by"] = actor
    data["updated_at"] = now

    add_character(data)

    context.user_data.pop(
        "new_build",
        None
    )

    context.user_data.pop(
        "add_current_field",
        None
    )

    await query.edit_message_text(
        "✅ Build saved successfully.",
        reply_markup=build_management_keyboard()
    )

    return ConversationHandler.END


async def build_cancel(update, context):

    query = update.callback_query
    await query.answer()

    context.user_data.pop(
        "new_build",
        None
    )

    context.user_data.pop(
        "add_current_field",
        None
    )

    await query.edit_message_text(
        "❌ Add Build cancelled.",
        reply_markup=build_management_keyboard()
    )

    return ConversationHandler.END


# =========================================================
# PRE-SAVE EDIT
# =========================================================

PRE_EDIT_SELECT = 100
PRE_EDIT_VALUE = 101


def pre_edit_keyboard():

    buttons = []

    for field, title in FIELDS:

        buttons.append([
            InlineKeyboardButton(
                title,
                callback_data=f"pre_edit_field_{field}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="pre_edit_back"
        )
    ])

    return InlineKeyboardMarkup(buttons)


def pre_edit_value_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🗑️ Clear",
                callback_data="pre_edit_clear"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="pre_edit_value_back"
            )
        ],
    ])


async def build_edit_sections(update, context):

    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            "❌ You do not have permission."
        )
        return ConversationHandler.END

    if "new_build" not in context.user_data:
        await query.edit_message_text(
            "❌ No builds available to edit."
        )
        return ConversationHandler.END

    await query.edit_message_text(
        "✏️ Edit Sections\n\n"
        "Select the section you want to edit:",
        reply_markup=pre_edit_keyboard()
    )

    return PRE_EDIT_SELECT


async def pre_edit_select(update, context):

    query = update.callback_query
    await query.answer()

    field = query.data.replace(
        "pre_edit_field_",
        ""
    )

    if field not in FIELD_TITLES:
        return PRE_EDIT_SELECT

    context.user_data["pre_edit_field"] = field

    value = context.user_data[
        "new_build"
    ].get(
        field,
        ""
    )

    await query.edit_message_text(
        f"✏️ Edit {FIELD_TITLES[field]}\n\n"
        "Send the new value.\n\n"
        "Current value:\n"
        f"{value if value else 'Empty'}",
        reply_markup=pre_edit_value_keyboard()
    )

    return PRE_EDIT_VALUE


async def pre_edit_enter_value(update, context):

    field = context.user_data.get(
        "pre_edit_field"
    )

    if not field:
        return PRE_EDIT_SELECT

    context.user_data[
        "new_build"
    ][field] = update.message.text

    await update.message.reply_text(
        "✅ Change saved.\n\n"
        "Select another section:",
        reply_markup=pre_edit_keyboard()
    )

    return PRE_EDIT_SELECT


async def pre_edit_clear(update, context):

    query = update.callback_query
    await query.answer()

    field = context.user_data.get(
        "pre_edit_field"
    )

    if field:

        context.user_data[
            "new_build"
        ][field] = ""

    await query.edit_message_text(
        "🗑️ This section was cleared.\n\n"
        "Select another section:",
        reply_markup=pre_edit_keyboard()
    )

    return PRE_EDIT_SELECT


async def pre_edit_value_back(update, context):

    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "✏️ Edit Sections\n\n"
        "Select the section you want to edit:",
        reply_markup=pre_edit_keyboard()
    )

    return PRE_EDIT_SELECT


async def pre_edit_back(update, context):

    query = update.callback_query
    await query.answer()

    await show_finish_add(
        update,
        context
    )

    return ConversationHandler.END


# =========================================================
# EDIT EXISTING CHARACTER
# =========================================================

EDIT_CHARACTER_SELECT = 200
EDIT_FIELD_SELECT = 201
EDIT_VALUE = 202


async def edit_character_start(update, context):

    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            "❌ You do not have permission."
        )
        return ConversationHandler.END

    characters = get_all_characters()

    if not characters:

        await query.edit_message_text(
            "❌ No characters have been added yet.",
            reply_markup=build_management_keyboard()
        )

        return ConversationHandler.END

    keyboard = []

    for character in characters:

        keyboard.append([
            InlineKeyboardButton(
                character["name"],
                callback_data=f"edit_character_{character['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="edit_characters_back_menu"
        )
    ])

    await query.edit_message_text(
        "✏️ Edit Build\n\n"
        "Select a character:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return EDIT_CHARACTER_SELECT


async def edit_character_back_menu(update, context):

    query = update.callback_query
    await query.answer()

    context.user_data.pop(
        "edit_character_id",
        None
    )

    context.user_data.pop(
        "edit_field",
        None
    )

    await query.edit_message_text(
        "📚 Build Management\n\n"
        "Select an operation:",
        reply_markup=build_management_keyboard()
    )

    return ConversationHandler.END


async def edit_select_character(update, context):

    query = update.callback_query
    await query.answer()

    try:

        character_id = int(
            query.data.replace(
                "edit_character_",
                ""
            )
        )

    except ValueError:

        await query.answer(
            "❌ Invalid character.",
            show_alert=True
        )

        return EDIT_CHARACTER_SELECT

    character = get_character(
        character_id
    )

    if not character:

        await query.edit_message_text(
            "❌ Character not found.",
            reply_markup=build_management_keyboard()
        )

        return ConversationHandler.END

    context.user_data[
        "edit_character_id"
    ] = character_id

    await show_edit_fields(
        update,
        context,
        character
    )

    return EDIT_FIELD_SELECT


async def show_edit_fields(update, context, character=None):

    if character is None:

        character_id = context.user_data.get(
            "edit_character_id"
        )

        character = get_character(
            character_id
        )

    if not character:

        if update.callback_query:

            await update.callback_query.edit_message_text(
                "❌ Character not found.",
                reply_markup=build_management_keyboard()
            )

        return

    keyboard = []

    for field, title in FIELDS:

        keyboard.append([
            InlineKeyboardButton(
                title,
                callback_data=f"edit_field_{field}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "💾 Save",
            callback_data="edit_finish"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="edit_back_characters"
        )
    ])

    text = (
        f"✏️ Edit {character['name']}\n\n"
        "Select the section you want to edit:"
    )

    if update.callback_query:

        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def edit_select_field(update, context):

    query = update.callback_query
    await query.answer()

    field = query.data.replace(
        "edit_field_",
        ""
    )

    if field not in FIELD_TITLES:

        await query.answer(
            "❌ Invalid section.",
            show_alert=True
        )

        return EDIT_FIELD_SELECT

    character_id = context.user_data.get(
        "edit_character_id"
    )

    character = get_character(
        character_id
    )

    if not character:

        await query.edit_message_text(
            "❌ Character not found.",
            reply_markup=build_management_keyboard()
        )

        return ConversationHandler.END

    context.user_data[
        "edit_field"
    ] = field

    current_value = character[field] or ""

    await query.edit_message_text(
        f"✏️ Edit {FIELD_TITLES[field]}\n\n"
        "Send the new value.\n\n"
        "Current value:\n"
        f"{current_value if current_value else 'Empty'}",
        reply_markup=edit_value_keyboard()
    )

    return EDIT_VALUE


def edit_value_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🗑️ Clear",
                callback_data="edit_clear_field"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="edit_value_back"
            )
        ],
    ])


async def edit_enter_value(update, context):

    field = context.user_data.get(
        "edit_field"
    )

    character_id = context.user_data.get(
        "edit_character_id"
    )

    if not field or not character_id:

        await update.message.reply_text(
            "❌ Edit data not found."
        )

        return ConversationHandler.END

    value = update.message.text

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = update.effective_user
    actor = user.username or user.full_name or str(user.id)

    update_character(
        character_id,
        field,
        value,
        updated_by=actor,
        updated_at=now
    )

    await update.message.reply_text(
        "✅ Change saved successfully."
    )

    character = get_character(
        character_id
    )

    await send_edit_fields_message(
        update,
        context,
        character
    )

    return EDIT_FIELD_SELECT


async def send_edit_fields_message(
    update,
    context,
    character
):

    keyboard = []

    for field, title in FIELDS:

        keyboard.append([
            InlineKeyboardButton(
                title,
                callback_data=f"edit_field_{field}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "💾 Save",
            callback_data="edit_finish"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="edit_back_characters"
        )
    ])

    await update.message.reply_text(
        f"✏️ Edit {character['name']}\n\n"
        "Select another section:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def edit_clear_field(update, context):

    query = update.callback_query
    await query.answer()

    field = context.user_data.get(
        "edit_field"
    )

    character_id = context.user_data.get(
        "edit_character_id"
    )

    if not field or not character_id:

        await query.edit_message_text(
            "❌ Edit data not found."
        )

        return ConversationHandler.END

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = update.effective_user
    actor = user.username or user.full_name or str(user.id)

    update_character(
        character_id,
        field,
        "",
        updated_by=actor,
        updated_at=now
    )

    character = get_character(
        character_id
    )

    await query.edit_message_text(
        f"🗑 {FIELD_TITLES[field]} was cleared.\n\n"
        f"✏️ Edit {character['name']}\n\n"
        "Select another section:",
        reply_markup=edit_fields_keyboard()
    )

    return EDIT_FIELD_SELECT


def edit_fields_keyboard():

    buttons = []

    for field, title in FIELDS:

        buttons.append([
            InlineKeyboardButton(
                title,
                callback_data=f"edit_field_{field}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "💾 Save",
            callback_data="edit_finish"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="edit_back_characters"
        )
    ])

    return InlineKeyboardMarkup(buttons)


async def edit_value_back(update, context):

    query = update.callback_query
    await query.answer()

    character_id = context.user_data.get(
        "edit_character_id"
    )

    character = get_character(
        character_id
    )

    if not character:

        await query.edit_message_text(
            "❌ Character not found.",
            reply_markup=build_management_keyboard()
        )

        return ConversationHandler.END

    await show_edit_fields(
        update,
        context,
        character
    )

    return EDIT_FIELD_SELECT


async def edit_back_characters(update, context):

    query = update.callback_query
    await query.answer()

    context.user_data.pop(
        "edit_field",
        None
    )

    characters = get_all_characters()

    keyboard = []

    for character in characters:

        keyboard.append([
            InlineKeyboardButton(
                character["name"],
                callback_data=f"edit_character_{character['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="edit_characters_back_menu"
        )
    ])

    await query.edit_message_text(
        "✏️ Edit Build\n\n"
        "Select a character:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return EDIT_CHARACTER_SELECT


async def edit_finish(update, context):

    query = update.callback_query
    await query.answer()

    character_id = context.user_data.get(
        "edit_character_id"
    )

    character = get_character(
        character_id
    )

    context.user_data.pop(
        "edit_character_id",
        None
    )

    context.user_data.pop(
        "edit_field",
        None
    )

    if character:

        await query.edit_message_text(
            f"✅ Edit \"{character['name']}\" completed.",
            reply_markup=build_management_keyboard()
        )

    else:

        await query.edit_message_text(
            "✅ Edit completed.",
            reply_markup=build_management_keyboard()
        )

    return ConversationHandler.END


# =========================================================
# ELEMENTS -> CHARACTERS -> DETAILS
# =========================================================

def elements_keyboard():
    buttons = []
    for key, label in ELEMENTS.items():
        buttons.append([InlineKeyboardButton(label, callback_data=f"admin_element_{key}")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_build_menu")])
    return InlineKeyboardMarkup(buttons)


async def admin_elements(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ You do not have permission.")
        return
    await query.edit_message_text("🧩 Elements\n\nSelect an element:", reply_markup=elements_keyboard())


async def admin_element_characters(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ You do not have permission.")
        return
    element = query.data.replace("admin_element_", "")
    if element not in ELEMENTS:
        await query.answer("Invalid element.", show_alert=True)
        return
    characters = get_characters_by_element(element)
    buttons = []
    for character in characters:
        buttons.append([InlineKeyboardButton(character["name"], callback_data=f"admin_element_character_{character['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_elements")])
    if not characters:
        text = f"{ELEMENTS[element]}\n\nNo characters have been added to this element yet."
    else:
        text = f"{ELEMENTS[element]}\n\nSelect a character:"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def admin_character_details(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ You do not have permission.")
        return
    try:
        character_id = int(query.data.replace("admin_element_character_", ""))
    except ValueError:
        await query.answer("Invalid character.", show_alert=True)
        return
    character = get_character(character_id)
    if not character:
        await query.edit_message_text("❌ Character not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_elements")]]))
        return
    element_key = character["element"] or ""
    element = ELEMENTS.get(element_key, "Unknown")
    created_by = character["created_by"] or "Unknown"
    created_at = character["created_at"] or "Unknown"
    updated_by = character["updated_by"] or "Never"
    updated_at = character["updated_at"] or "Never"
    text = (
        f"📋 {character['name']}\n\n"
        f"Element: {element}\n\n"
        f"Created by: {created_by}\n"
        f"Created: {created_at}\n\n"
        f"Last updated by: {updated_by}\n"
        f"Last updated: {updated_at}"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"admin_element_{element_key}" if element_key in ELEMENTS else "admin_elements")]]))


# =========================================================
# DELETE CHARACTER
# =========================================================

async def delete_character_start(update, context):

    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            "❌ You do not have permission."
        )
        return

    characters = get_all_characters()

    if not characters:

        await query.edit_message_text(
            "❌ No characters available to delete.",
            reply_markup=build_management_keyboard()
        )

        return

    keyboard = []

    for character in characters:

        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {character['name']}",
                callback_data=f"delete_character_{character['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="admin_build_menu"
        )
    ])

    await query.edit_message_text(
        "🗑️ Delete Build\n\n"
        "Select the character you want to delete:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def delete_character_confirm(update, context):

    query = update.callback_query
    await query.answer()

    try:

        character_id = int(
            query.data.replace(
                "delete_character_",
                ""
            )
        )

    except ValueError:
        return

    character = get_character(
        character_id
    )

    if not character:

        await query.edit_message_text(
            "❌ Character not found.",
            reply_markup=build_management_keyboard()
        )

        return

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Yes, delete it",
                callback_data=f"confirm_delete_{character_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="admin_delete_character"
            )
        ],
    ]

    await query.edit_message_text(
        f"⚠️ Are you sure you want to delete\n"
        f"\"{character['name']}\"?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def confirm_delete_character(update, context):

    query = update.callback_query
    await query.answer()

    try:

        character_id = int(
            query.data.replace(
                "confirm_delete_",
                ""
            )
        )

    except ValueError:
        return

    character = get_character(
        character_id
    )

    if not character:

        await query.edit_message_text(
            "❌ Character not found.",
            reply_markup=build_management_keyboard()
        )

        return

    name = character["name"]

    delete_character(
        character_id
    )

    await query.edit_message_text(
        f'✅ Character "{name}" deleted.',
        reply_markup=build_management_keyboard()
    )


# =========================================================
# BACKUP MANAGEMENT
# =========================================================

async def admin_backup_menu(update, context):
    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        await query.edit_message_text("❌ Only the Owner can access backups.")
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💾 Manual Backup", callback_data="backup_manual"),
            InlineKeyboardButton("♻️ Restore", callback_data="backup_restore"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
    ])

    await query.edit_message_text(
        "🗄️ Backup\n\nSelect an operation:",
        reply_markup=keyboard,
    )


async def manual_backup(update, context):
    query = update.callback_query
    await query.answer("Creating backup...")

    if not is_owner(update.effective_user.id):
        return

    try:
        backup_path = create_manual_backup()
        with open(backup_path, "rb") as document:
            await query.message.reply_document(
                document=document,
                caption="✅ Manual database backup created successfully."
            )

        await query.edit_message_text(
            "🗄️ Backup\n\n"
            "✅ Backup created and sent successfully.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💾 Manual Backup", callback_data="backup_manual"),
                 InlineKeyboardButton("♻️ Restore", callback_data="backup_restore")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
            ])
        )
    except Exception as exc:
        await query.edit_message_text(
            f"❌ Backup failed.\n\n{exc}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_backup")]
            ])
        )


async def restore_start(update, context):
    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        return ConversationHandler.END

    await query.edit_message_text(
        "♻️ Restore Database\n\n"
        "Send the .db backup file here.\n\n"
        "⚠️ The current database will be backed up automatically before restore."
    )
    return RESTORE_FILE


async def restore_receive_file(update, context):
    if not is_owner(update.effective_user.id):
        return ConversationHandler.END

    document = update.message.document
    if document is None:
        await update.message.reply_text("❌ Please send a database file (.db).")
        return RESTORE_FILE

    file_name = document.file_name or "backup.db"
    if not file_name.lower().endswith(".db"):
        await update.message.reply_text("❌ Please send a .db SQLite backup file.")
        return RESTORE_FILE

    if document.file_size and document.file_size > 50 * 1024 * 1024:
        await update.message.reply_text("❌ The backup file is too large. Maximum size is 50 MB.")
        return RESTORE_FILE

    os.makedirs("data", exist_ok=True)
    pending_path = os.path.join(
        "data",
        f"restore_pending_{update.effective_user.id}.db"
    )

    try:
        telegram_file = await context.bot.get_file(document.file_id)
        await telegram_file.download_to_drive(pending_path)

        if not validate_sqlite_backup(pending_path):
            os.remove(pending_path)
            await update.message.reply_text(
                "❌ This file is not a valid SQLite database backup."
            )
            return RESTORE_FILE

        context.user_data["pending_restore"] = pending_path
        context.user_data["pending_restore_name"] = file_name

        await update.message.reply_text(
            f"♻️ Restore confirmation\n\n"
            f"File: {file_name}\n\n"
            "⚠️ The current database will be backed up first, then replaced with this file.\n\n"
            "Do you want to continue?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Confirm Restore", callback_data="backup_restore_confirm"),
                    InlineKeyboardButton("❌ Cancel", callback_data="backup_restore_cancel"),
                ]
            ])
        )
        return RESTORE_CONFIRM
    except Exception as exc:
        try:
            if os.path.exists(pending_path):
                os.remove(pending_path)
        except Exception:
            pass
        await update.message.reply_text(f"❌ Could not read the backup file.\n\n{exc}")
        return RESTORE_FILE


async def restore_confirm(update, context):
    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        return ConversationHandler.END

    pending_path = context.user_data.get("pending_restore")
    if not pending_path or not os.path.exists(pending_path):
        await query.edit_message_text("❌ The pending restore file is no longer available.")
        return ConversationHandler.END

    try:
        safety_backup = restore_database_from_file(pending_path)
        file_name = context.user_data.get("pending_restore_name", "backup.db")
        await query.edit_message_text(
            "♻️ Restore Database\n\n"
            f"✅ Restored successfully from: {file_name}\n\n"
            "A safety backup of the previous database was created before the restore."
        )
        context.user_data.pop("pending_restore", None)
        context.user_data.pop("pending_restore_name", None)
        try:
            os.remove(pending_path)
        except Exception:
            pass
        return ConversationHandler.END
    except Exception as exc:
        await query.edit_message_text(f"❌ Restore failed.\n\n{exc}")
        return ConversationHandler.END


async def restore_cancel(update, context):
    query = update.callback_query
    await query.answer()
    pending_path = context.user_data.pop("pending_restore", None)
    context.user_data.pop("pending_restore_name", None)
    if pending_path:
        try:
            if os.path.exists(pending_path):
                os.remove(pending_path)
        except Exception:
            pass
    await query.edit_message_text(
        "🗄️ Backup\n\nRestore cancelled.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💾 Manual Backup", callback_data="backup_manual"),
             InlineKeyboardButton("♻️ Restore", callback_data="backup_restore")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
        ])
    )
    return ConversationHandler.END


# =========================================================
# BROADCAST
# =========================================================

BROADCAST_MESSAGE = 410
BROADCAST_CONFIRM = 411
RESTORE_FILE = 420
RESTORE_CONFIRM = 421


async def broadcast_start(update, context):
    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        await query.edit_message_text("❌ Only the Owner can send broadcasts.")
        return ConversationHandler.END

    await query.edit_message_text(
        "📢 Broadcast\n\n"
        "Send the message you want to broadcast to all users.\n\n"
        "You can use Persian or English text."
    )
    return BROADCAST_MESSAGE


async def broadcast_receive(update, context):
    if not is_owner(update.effective_user.id):
        return ConversationHandler.END

    message = (update.message.text or "").strip()
    if not message:
        await update.message.reply_text("❌ The message cannot be empty.")
        return BROADCAST_MESSAGE

    context.user_data["broadcast_message"] = message

    await update.message.reply_text(
        "📢 Broadcast Preview\n\n"
        "────────────\n"
        f"{message}\n"
        "────────────\n\n"
        "Send this message to all registered users?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Send", callback_data="broadcast_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel"),
            ]
        ])
    )
    return BROADCAST_CONFIRM


async def broadcast_confirm(update, context):
    query = update.callback_query
    await query.answer("Sending broadcast...")

    if not is_owner(update.effective_user.id):
        return ConversationHandler.END

    message = context.user_data.get("broadcast_message")
    if not message:
        await query.edit_message_text("❌ Broadcast message not found.")
        return ConversationHandler.END

    users = get_all_user_ids()
    sent = 0
    failed = 0
    blocked = 0

    for user in users:
        chat_id = user["chat_id"]
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
            )
            sent += 1
            await asyncio.sleep(0.05)
        except RetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after) + 0.5)
            try:
                await context.bot.send_message(chat_id=chat_id, text=message)
                sent += 1
            except Exception:
                failed += 1
        except Forbidden:
            blocked += 1
        except Exception:
            failed += 1

    context.user_data.pop("broadcast_message", None)

    await query.edit_message_text(
        "📢 Broadcast Complete\n\n"
        f"✅ Sent: {sent}\n"
        f"🚫 Blocked: {blocked}\n"
        f"❌ Failed: {failed}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ])
    )
    return ConversationHandler.END


async def broadcast_cancel(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("broadcast_message", None)
    await query.edit_message_text(
        "📢 Broadcast cancelled.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ])
    )
    return ConversationHandler.END


def get_backup_conversation():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(restore_start, pattern=r"^backup_restore$")],
        states={
            RESTORE_FILE: [
                MessageHandler(filters.Document.ALL, restore_receive_file),
                CallbackQueryHandler(restore_cancel, pattern=r"^backup_restore_cancel$")
            ],
            RESTORE_CONFIRM: [
                CallbackQueryHandler(restore_confirm, pattern=r"^backup_restore_confirm$"),
                CallbackQueryHandler(restore_cancel, pattern=r"^backup_restore_cancel$")
            ],
        },
        fallbacks=[CallbackQueryHandler(restore_cancel, pattern=r"^backup_restore_cancel$")],
        allow_reentry=True,
    )


def get_broadcast_conversation():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_start, pattern=r"^admin_broadcast$")],
        states={
            BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_receive),
            ],
            BROADCAST_CONFIRM: [
                CallbackQueryHandler(broadcast_confirm, pattern=r"^broadcast_confirm$"),
                CallbackQueryHandler(broadcast_cancel, pattern=r"^broadcast_cancel$"),
            ],
        },
        fallbacks=[CallbackQueryHandler(broadcast_cancel, pattern=r"^broadcast_cancel$")],
        allow_reentry=True,
    )


# =========================================================
# BOT MANAGEMENT
# =========================================================

async def admin_bot_management(update, context):

    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        await query.edit_message_text(
            "❌ Only the Owner can access this section."
        )
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "👑 Owner Management",
                callback_data="owner_management"
            )
        ],
        [
            InlineKeyboardButton(
                "🛠️ Admin Management",
                callback_data="admin_management"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Admin List",
                callback_data="admin_list"
            )
        ],
        [
            InlineKeyboardButton(
                "📡 Ping",
                callback_data="admin_ping"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="admin_main"
            )
        ],
    ]

    await query.edit_message_text(
        "🤖 Bot Management\n\n"
        "Select a section:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# PING
# =========================================================


def ping_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Ping", callback_data="admin_ping_bot"),
            InlineKeyboardButton("🗄️ Ping-Database", callback_data="admin_ping_database"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="admin_bot_management")
        ],
    ])


async def admin_ping_menu(update, context):
    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        await query.edit_message_text(
            "❌ Only the Owner can access this section."
        )
        return

    await query.edit_message_text(
        "📡 Ping\n\n"
        "Select a test:",
        reply_markup=ping_keyboard()
    )


async def ping_bot_callback(update, context):
    query = update.callback_query

    if not is_owner(update.effective_user.id):
        await query.answer("❌ Owner only.", show_alert=True)
        return

    start = time.perf_counter()

    try:
        bot = await context.bot.get_me()
        elapsed_ms = (time.perf_counter() - start) * 1000

        ping_logger.info(
            "Bot Ping | User ID: %s | Bot: @%s | Latency: %.2f ms",
            update.effective_user.id,
            bot.username or "unknown",
            elapsed_ms
        )

        await query.answer()
        await query.edit_message_text(
            "⚡ Ping\n\n"
            f"Status: ONLINE\n"
            f"Latency: {elapsed_ms:.2f} ms\n"
            f"Bot: @{bot.username or 'unknown'}",
            reply_markup=ping_keyboard()
        )

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        ping_logger.exception(
            "Bot Ping Failed | User ID: %s | Elapsed: %.2f ms | Error: %s",
            update.effective_user.id,
            elapsed_ms,
            exc
        )
        await query.answer("Ping failed.", show_alert=True)


async def ping_database_callback(update, context):
    query = update.callback_query

    if not is_owner(update.effective_user.id):
        await query.answer("❌ Owner only.", show_alert=True)
        return

    start = time.perf_counter()
    connection = None

    try:
        connection = sqlite3.connect(DATABASE_PATH, timeout=5)
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        connection.close()
        connection = None

        elapsed_ms = (time.perf_counter() - start) * 1000

        ping_logger.info(
            "Database Ping | User ID: %s | Database: %s | Latency: %.2f ms",
            update.effective_user.id,
            DATABASE_PATH,
            elapsed_ms
        )

        await query.answer()
        await query.edit_message_text(
            "🗄️ Ping-Database\n\n"
            "Status: ONLINE\n"
            f"Query: SELECT 1\n"
            f"Latency: {elapsed_ms:.2f} ms",
            reply_markup=ping_keyboard()
        )

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        ping_logger.exception(
            "Database Ping Failed | User ID: %s | Elapsed: %.2f ms | Error: %s",
            update.effective_user.id,
            elapsed_ms,
            exc
        )
        await query.answer("Database ping failed.", show_alert=True)

    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


# =========================================================
# OWNER / ADMIN MANAGEMENT
# =========================================================

MANAGER_ID = 300
MANAGER_NAME = 301


async def owner_management(update, context):

    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Owner",
                callback_data="add_owner"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑️ Remove Owner",
                callback_data="remove_owner"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Owner List",
                callback_data="owner_list"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="admin_bot_management"
            )
        ],
    ]

    await query.edit_message_text(
        "👑 Owner Management",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_management(update, context):

    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Admin",
                callback_data="add_admin"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑️ Remove Admin",
                callback_data="remove_admin"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Admin List",
                callback_data="regular_admin_list"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="admin_bot_management"
            )
        ],
    ]

    await query.edit_message_text(
        "🛠️ Admin Management",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_list(update, context):

    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        return

    admins = get_all_admins()

    if not admins:

        text = "👥 No administrators found."

    else:

        lines = [
            "👥 Admin List",
            ""
        ]

        for item in admins:

            role = (
                "👑 Owner"
                if item["role"] == "owner"
                else "🛠️ Admin"
            )

            name = item["name"] or "Unnamed"

            lines.append(
                f"{role}\n"
                f"Name: {name}\n"
                f"ID: {item['user_id']}\n"
            )

        text = "\n".join(lines)

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="admin_bot_management"
                )
            ]
        ])
    )


async def owner_list(update, context):

    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        return

    owners = get_all_owners()

    lines = [
        "📋 Owner List",
        ""
    ]

    for item in owners:

        lines.append(
            f"👑 {item['name'] or 'Unnamed'}\n"
            f"ID: {item['user_id']}\n"
        )

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="owner_management"
                )
            ]
        ])
    )


async def regular_admin_list(update, context):

    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        return

    admins = get_all_regular_admins()

    if not admins:

        text = "📋 No regular admins found."

    else:

        lines = [
            "📋 Admin List",
            ""
        ]

        for item in admins:

            lines.append(
                f"🛠️ {item['name'] or 'Unnamed'}\n"
                f"ID: {item['user_id']}\n"
            )

        text = "\n".join(lines)

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="admin_management"
                )
            ]
        ])
    )


# =========================================================
# MANAGER CONVERSATION
# =========================================================

async def manager_start(update, context):

    query = update.callback_query
    await query.answer()

    if not is_owner(update.effective_user.id):
        return ConversationHandler.END

    action = query.data

    context.user_data[
        "manager_action"
    ] = action

    if action == "add_owner":

        await query.edit_message_text(
            "➕ Add Owner\n\n"
            "Send the user ID:"
        )

    elif action == "add_admin":

        await query.edit_message_text(
            "➕ Add Admin\n\n"
            "Send the user ID:"
        )

    elif action == "remove_owner":

        await query.edit_message_text(
            "🗑️ Remove Owner\n\n"
            "Send the user ID:"
        )

    elif action == "remove_admin":

        await query.edit_message_text(
            "🗑️ Remove Admin\n\n"
            "Send the user ID:"
        )

    return MANAGER_ID


async def manager_receive_id(update, context):

    text = update.message.text.strip()

    try:

        user_id = int(text)

    except ValueError:

        await update.message.reply_text(
            "❌ User ID must be numeric.\n\n"
            "Please send it again:"
        )

        return MANAGER_ID

    action = context.user_data.get(
        "manager_action"
    )

    # REMOVE
    if action in (
        "remove_owner",
        "remove_admin"
    ):

        if user_id == MAIN_OWNER_ID:

            await update.message.reply_text(
                "❌ The main Owner cannot be removed."
            )

            return MANAGER_ID

        target = get_admin(
            user_id
        )

        if not target:

            await update.message.reply_text(
                "❌ This user is not in the administrator list."
            )

            return MANAGER_ID

        expected_role = (
            "owner"
            if action == "remove_owner"
            else "admin"
        )

        if target["role"] != expected_role:

            await update.message.reply_text(
                "❌ This user role does not match the selected action. "
                ""
            )

            return MANAGER_ID

        remove_admin(
            user_id
        )

        await update.message.reply_text(
            "✅ User removed successfully.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data=(
                            "owner_management"
                            if expected_role == "owner"
                            else "admin_management"
                        )
                    )
                ]
            ])
        )

        context.user_data.pop(
            "manager_action",
            None
        )

        return ConversationHandler.END

    # ADD
    context.user_data[
        "manager_user_id"
    ] = user_id

    await update.message.reply_text(
        "👤 Now send the display name for this administrator:"
    )

    return MANAGER_NAME


async def manager_receive_name(update, context):

    name = update.message.text.strip()

    user_id = context.user_data.get(
        "manager_user_id"
    )

    action = context.user_data.get(
        "manager_action"
    )

    if not user_id:
        return ConversationHandler.END

    role = (
        "owner"
        if action == "add_owner"
        else "admin"
    )

    add_admin(
        user_id,
        role,
        name
    )

    context.user_data.pop(
        "manager_user_id",
        None
    )

    context.user_data.pop(
        "manager_action",
        None
    )

    await update.message.reply_text(
        f"✅ {('Owner' if role == 'owner' else 'Admin')} "
        "added successfully."
    )

    return ConversationHandler.END


# =========================================================
# CONVERSATION HANDLERS
# =========================================================

def get_add_character_conversation():

    return ConversationHandler(

        entry_points=[
            CallbackQueryHandler(
                add_character_start,
                pattern=r"^admin_add_character$"
            )
        ],

        states={

            ADD_ELEMENT: [
                CallbackQueryHandler(
                    add_element_selected,
                    pattern=r"^add_element_(pyro|hydro|anemo|cryo|electro|dendro|geo)$"
                ),
                CallbackQueryHandler(
                    add_close,
                    pattern=r"^add_close$"
                ),
            ],

            ADD_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "name"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
                CallbackQueryHandler(
                    add_close,
                    pattern=r"^add_close$"
                ),
            ],

            ADD_WEAPONS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "weapons"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_WEAPONS_NOTES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "weapons_notes"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_CONSTELLATION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "constellation"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_ARTIFACT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "artifact"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_ARTIFACT_NOTES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "artifact_notes"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_MAIN_STATS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "main_stats"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_SUB_STATS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "sub_stats"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_SUB_STATS_NOTES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "sub_stats_notes"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_STAT_GOALS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "stat_goals"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_TALENTS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "talents"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_TEAMS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "teams"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_ROTATION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "rotation"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_NOTES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "notes"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_C1: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "c1"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_C2: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "c2"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_C3: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "c3"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_C4: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "c4"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_C5: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "c5"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],

            ADD_C6: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: add_receive(
                        u, c, "c6"
                    )
                ),
                CallbackQueryHandler(
                    add_next,
                    pattern=r"^add_next$"
                ),
                CallbackQueryHandler(
                    add_back,
                    pattern=r"^add_back$"
                ),
            ],
        },

        fallbacks=[
            CommandHandler(
                "cancel",
                build_cancel
            )
        ],

        allow_reentry=True,
    )


def get_pre_save_edit_conversation():

    return ConversationHandler(

        entry_points=[
            CallbackQueryHandler(
                build_edit_sections,
                pattern=r"^build_edit_sections$"
            )
        ],

        states={

            PRE_EDIT_SELECT: [
                CallbackQueryHandler(
                    pre_edit_select,
                    pattern=r"^pre_edit_field_[a-z0-9_]+$"
                ),
                CallbackQueryHandler(
                    pre_edit_back,
                    pattern=r"^pre_edit_back$"
                ),
            ],

            PRE_EDIT_VALUE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    pre_edit_enter_value
                ),
                CallbackQueryHandler(
                    pre_edit_clear,
                    pattern=r"^pre_edit_clear$"
                ),
                CallbackQueryHandler(
                    pre_edit_value_back,
                    pattern=r"^pre_edit_value_back$"
                ),
            ],
        },

        fallbacks=[],

        allow_reentry=True,
    )


def get_edit_character_conversation():

    return ConversationHandler(

        entry_points=[
            CallbackQueryHandler(
                edit_character_start,
                pattern=r"^admin_edit_character$"
            )
        ],

        states={

            EDIT_CHARACTER_SELECT: [
                CallbackQueryHandler(
                    edit_select_character,
                    pattern=r"^edit_character_[0-9]+$"
                ),
                CallbackQueryHandler(
                    edit_character_back_menu,
                    pattern=r"^edit_characters_back_menu$"
                ),
            ],

            EDIT_FIELD_SELECT: [
                CallbackQueryHandler(
                    edit_select_field,
                    pattern=r"^edit_field_[a-z0-9_]+$"
                ),
                CallbackQueryHandler(
                    edit_finish,
                    pattern=r"^edit_finish$"
                ),
                CallbackQueryHandler(
                    edit_back_characters,
                    pattern=r"^edit_back_characters$"
                ),
            ],

            EDIT_VALUE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    edit_enter_value
                ),
                CallbackQueryHandler(
                    edit_clear_field,
                    pattern=r"^edit_clear_field$"
                ),
                CallbackQueryHandler(
                    edit_value_back,
                    pattern=r"^edit_value_back$"
                ),
            ],
        },

        fallbacks=[],

        allow_reentry=True,
    )


def get_manager_conversation():

    return ConversationHandler(

        entry_points=[
            CallbackQueryHandler(
                manager_start,
                pattern=r"^(add_owner|add_admin|remove_owner|remove_admin)$"
            )
        ],

        states={

            MANAGER_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    manager_receive_id
                )
            ],

            MANAGER_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    manager_receive_name
                )
            ],
        },

        fallbacks=[],

        allow_reentry=True,
    )