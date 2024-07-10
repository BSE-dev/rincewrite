"""Welcome to Reflex! This file outlines the steps to create a basic app."""

from typing import Any
import reflex as rx  # type: ignore
# Reflex does not provide type hints at the moment

piece_desc_placeholder = "Your piece description here. Any description that \
can help bootstrap the structuration of your piece is most welcome (title, \
chapters...). Anything about its contents is also welcome (subject, themes, \
characters, plot, ...). But don't waste too much time here: we will build \
this and the rest along the way, together."
user_desc_placeholder = "Your own description here. Any description that can \
help me bootstrap my behaviour towards you is most welcome (why do you write?\
, what do you like to write? ...). Anything about your character is also \
welcome (what are you trying to achieve by writing?, how do you like to be \
adressed? ...). But don't waste too much time here: we will build this and \
the rest along the way, together."


class RWState(rx.State):  # type: ignore
    """The app state."""

    show_dialog: bool = True
    piece_name: str = ""
    piece_desc: str = ""
    piece_form_submitted: bool = False
    user_name: str = ""
    user_desc: str = ""
    editor_content: str = ""

    def toggle_dialog(self, _toggle_dialog: bool) -> None:
        self.show_dialog = not self.show_dialog
        print("Launch graph can go there")

    def handle_piece_submit(self, data: dict[str, Any]) -> None:
        self.piece_name = data["piece_name"]
        self.piece_desc = data["piece_desc"]
        self.piece_form_submitted = True

    def handle_user_submit(self, data: dict[str, Any]) -> None:
        self.user_name = data["piece_name"]
        self.user_desc = data["piece_desc"]
        self.show_dialog = False
        self.editor_content = f"Hello {self.user_name}! Let's write together."

    def text_changed(self, changed_txt: str) -> None:
        self.editor_content = changed_txt


def welcome_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title(
                    rx.heading("Welcome to... me! I'm Rincewrite", size="5"),),
                rx.dialog.description(
                    rx.text(
                        "I will help you from start to finish with your piece \
                        of writing.",
                        align="center"),
                ),
                rx.cond(
                    ~RWState.piece_form_submitted,
                    rx.form(
                        rx.vstack(
                            rx.text("If you would just tell me which it is.",
                                    align="center",
                                    color_scheme="blue",),
                            rx.input(
                                placeholder="Your piece name here...",
                                name="piece_name",
                            ),
                            rx.text_area(
                                placeholder=piece_desc_placeholder,
                                style={
                                    "& ::placeholder": {
                                        "text-align": "justify"
                                    },
                                },
                                rows="10",
                                width="100%",
                                name="piece_desc",
                            ),
                            rx.button("begin", type="submit"),
                            spacing="3",
                            justify="center",
                            align="center",
                        ),
                        on_submit=RWState.handle_piece_submit,
                        # for some reason, Reflex will serve the form data to
                        # the alternative one ('user' form) if reset_on_submit
                        # is not set
                        reset_on_submit=True,
                    ),
                    rx.form(
                        rx.vstack(
                            rx.text("If you would just tell me who you are.",
                                    align="center",
                                    color_scheme="blue",),
                            rx.input(
                                placeholder="Your own name here...",
                                name="piece_name",
                            ),
                            rx.text_area(
                                placeholder=user_desc_placeholder,
                                style={
                                    "& ::placeholder": {
                                        "text-align": "justify"
                                    },
                                },
                                rows="10",
                                width="100%",
                                name="piece_desc",
                            ),
                            rx.dialog.close(
                                rx.button("truly begin now", type="submit"),),
                            spacing="3",
                            justify="center",
                            align="center",
                        ),
                        on_submit=RWState.handle_user_submit,
                    ),
                ),
                rx.text(
                    "conjured ",
                    rx.code("@ Brest Social Engines"),
                ),
                rx.logo(),
                spacing="3",
                justify="center",
                align="center",
                min_height="50vh",
            ),
            # prevevent the dialog from closing in any other way than clicking
            # the 'begin' button
            on_escape_key_down=rx.prevent_default,
            on_interact_outside=rx.prevent_default,
        ),
        open=RWState.show_dialog,
        on_open_change=RWState.toggle_dialog,
    )


def app_content() -> rx.Component:
    return rx.text_area(
        value=RWState.editor_content,
        on_change=RWState.text_changed,
        placeholder="Begin here...",
        width="100vw",
        height="100vh",
    )


def index() -> rx.Component:
    return rx.box(
        rx.color_mode.button(position="top-right"),
        welcome_dialog(),
        app_content(),
        width="100vw",
        height="100vh",
    )


app = rx.App()
app.add_page(index, title="Rincewrite")
