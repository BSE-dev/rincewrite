"""Welcome to Reflex! This file outlines the steps to create a basic app."""

from io import BytesIO
from typing import Annotated, Any, AsyncGenerator
from typing_extensions import TypedDict
from PIL import Image  # type: ignore
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver
from langchain_openai import ChatOpenAI
from langchain import hub
from langchain_core.messages.base import BaseMessage
from langchain_core.runnables import RunnableConfig
import reflex as rx  # type: ignore
# Reflex does not provide type hints at the moment

model = ChatOpenAI(model='gpt-3.5-turbo', temperature=0.7, streaming=True)
# model = ChatOpenAI(model='gpt-4o', temperature=0.7, streaming=True)

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


class GraphState(TypedDict):

    piece_name: str
    piece_desc: str
    user_name: str
    user_desc: str
    messages: Annotated[list[BaseMessage], add_messages]


# 'welcome' Node
_welcome_prompt = hub.pull("rincewrite-welcome")
_welcome_chain = _welcome_prompt | model


async def _welcome(state: GraphState) -> dict[str, Any]:

    welcome_msg = await _welcome_chain.ainvoke({
        "piece_name":   state["piece_name"],
        "piece_desc":   state["piece_desc"],
        "user_name":    state["user_name"],
        "user_desc":    state["user_desc"],
    })

    return {"messages": [welcome_msg]}

# 'user_action' Node


def _user_action(state: GraphState) -> None:
    # this is a 'fake' node, serving as en entry point for the user's actions
    pass


# 'chat' Node
_chat_prompt = hub.pull("rincewrite-chat")
_chat_chain = _chat_prompt | model


async def _chat(state: GraphState) -> dict[str, Any]:

    chat_msg = await _chat_chain.ainvoke(state["messages"])

    return {"messages": [chat_msg]}


# memory = SqliteSaver.from_conn_string(":memory:")
memory = AsyncSqliteSaver.from_conn_string(":memory:")

graph_builder = StateGraph(GraphState)
graph_builder.add_node("welcome", _welcome)
graph_builder.add_node("user_action", _user_action)
graph_builder.add_node("chat", _chat)

graph_builder.set_entry_point("welcome")
graph_builder.add_edge("welcome", "user_action")
graph_builder.add_edge("user_action", "chat")
graph_builder.add_edge("chat", "user_action")
graph = graph_builder.compile(
    checkpointer=memory,
    interrupt_before=["user_action"]
)

# img_data = graph.get_graph().draw_mermaid_png()
# img = Image.open(BytesIO(img_data))
# img.show()


class RWState(rx.State):  # type: ignore
    """The app state."""
    # intro dialog
    show_dialog: bool = True
    piece_form_submitted: bool = False
    # main app col 1/3 : chat / workzone
    messages: list[dict[str, str]] = []
    service_button: str = "answer"  # proposed service will be situational
    # main app col 2/3 : action buttons
    buttons: list[str] = [  # proposed robot actions will be situational
        "i have no idea what i'm doing",
        "help me structure the thing",
        "i have a draft already"
    ]
    # main app col 3/3 : render zone
    renderer_content: str = ""

    # backend state
    _piece_name: str = ""
    _piece_desc: str = ""
    _user_name: str = ""
    _user_desc: str = ""

    def handle_piece_submit(self, data: dict[str, Any]) -> None:
        self._piece_name = data["piece_name"]
        self._piece_desc = data["piece_desc"]
        self.piece_form_submitted = True

    async def welcome(
        self, data: dict[str, Any]
    ) -> AsyncGenerator[None, None]:
        self._user_name = data["piece_name"]
        self._user_desc = data["piece_desc"]
        self.show_dialog = False
        yield

        self.renderer_content = f"# {self._piece_name}\n\n{self._piece_desc}\n\n"
        yield

        config = RunnableConfig({"configurable": {"thread_id": "1"}})

        # # direct call to the full graph
        # res = graph.invoke({
        #     "piece_name":  self._piece_name,
        #     "piece_desc":  self._piece_desc,
        #     "user_name":   self._user_name,
        #     "user_desc":   self._user_desc,
        #     "messages":    [],},
        #     config)
        # # do something

        # # stream State
        # for event in graph.stream({
        #         "piece_name":   self._piece_name,
        #         "piece_desc":   self._piece_desc,
        #         "user_name":    self._user_name,
        #         "user_desc":    self._user_desc,
        #         "messages":     [], },
        #         config):
        #     for value in event.values():
        #         self.messages.append({
        #             'type': value["messages"][-1].type,
        #             'msg': value["messages"][-1].content,
        #         })
        #         yield

        # stream LLM tokens
        self.messages.append({
            'type': "ai",
            'msg': "",
        })
        async for event in graph.astream_events(
            {"piece_name":  self._piece_name,
             "piece_desc":  self._piece_desc,
             "user_name":   self._user_name,
             "user_desc":   self._user_desc,
             "messages":    [], },
            config,
            version="v2"
        ):
            kind = event["event"]
            # emitted for each streamed token
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                # only display non-empty content (not tool calls)
                if content:
                    self.messages[-1]["msg"] += content
                    yield

    async def handle_user_msg_submit(
        self,
        data: dict[str, Any]
    ) -> AsyncGenerator[None, None]:
        self.messages.append({"type": "user", "msg": data["text_area_input"]})
        yield
        config = RunnableConfig({"configurable": {"thread_id": "1"}})
        # manually update graph state
        await graph.aupdate_state(
            config,
            {"messages": [data["text_area_input"]]},
            as_node="user_action")
        # # resume graph execution and stream state
        # for event in graph.stream(None, config):
        #     for value in event.values():
        #         self.messages.append({
        #             'type': value["messages"][-1].type,
        #             'msg': value["messages"][-1].content,
        #         })
        #         yield
        # resume graph execution and stream LLM tokens
        self.messages.append({
            'type': "ai",
            'msg': "",
        })
        async for event in graph.astream_events(
            None,
            config,
            version="v2"
        ):
            kind = event["event"]
            # emitted for each streamed token
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                # only display non-empty content (not tool calls)
                if content:
                    self.messages[-1]["msg"] += content
                    yield


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
                        on_submit=RWState.welcome,
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
    )


def chat_msg(msg: dict[str, str]) -> rx.Component:
    return rx.box(
        rx.markdown(
            msg["msg"],
            background_color=rx.cond(
                msg["type"] == "user",
                rx.color("mauve", 4),
                rx.color("accent", 4)
            ),
            color=rx.cond(
                msg["type"] == "user",
                rx.color("mauve", 12),
                rx.color("accent", 12),
            ),
            style={
                "display": "inline-block",
                "padding": "0.5em",
                "border_radius": "8px",
                "max_width": ["30em", "30em", "50em", "50em", "50em", "50em"],
            },
        ),
        align_self=rx.cond(
            msg["type"] == "user",
            "flex-end",
            "flex-start"
        ),
    )


def chat_messages() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.foreach(
                RWState.messages,
                chat_msg
            ),
            spacing="1",
            width="98%",
        ),
        width="100%",
    )


def draft_area() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.scroll_area(
                chat_messages(),
                type="always",
                scrollbars="vertical",
                width="95%",
                height="59%",
            ),
            rx.form(
                rx.vstack(
                    rx.text_area(
                        placeholder="Work from here...",
                        name="text_area_input",
                        width="100%",
                        height="100%",
                    ),
                    rx.button(
                        RWState.service_button,
                        type="submit",
                        color_scheme="blue",
                        width="40%",
                        style={"font_size": "14px"},
                    ),
                    spacing="2",
                    justify="center",
                    align="center",
                    height="100%",
                ),
                width="95%",
                height="39%",
                on_submit=RWState.handle_user_msg_submit,
                reset_on_submit=True,
            ),
            spacing="3",
            justify="center",
            align="center",
            width="100%",
            height="95%",
        ),
        width="100%",
        height="100%",
    )


def action_button(button: str) -> rx.Component:
    return rx.button(
        button,
        color_scheme="blue",
        width="90%",
        height="auto",
        style={"font_size": "14px"},
    )


def action_buttons() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.foreach(
                RWState.buttons,
                action_button,
            ),
            spacing="5",
            justify="center",
            align="center",
        ),
        width="100%",
        height="100%",
    ),


def app_content() -> rx.Component:
    return rx.flex(
        rx.box(
            draft_area(),
            width="45%",
        ),
        rx.box(
            action_buttons(),
            width="10%",
        ),
        rx.box(
            rx.center(
                rx.scroll_area(
                    rx.center(
                        rx.markdown(
                            RWState.renderer_content,
                            width="98%",
                            bg="green",
                        ),
                        width="100%",
                        height="100%",
                    ),
                    type="always",
                    scrollbars="vertical",
                    width="95%",
                    height="90%",
                    bg="yellow",
                ),
                width="100%",
                height="100%",
            ),
            width="45%",
            height="100%",
        ),
        width="100%",
        height="100%",
    )


def index() -> rx.Component:
    return rx.box(
        rx.color_mode.button(position="top-right"),
        welcome_dialog(),
        app_content(),
        width="100vw",
        height="100vh",
        overflow="hidden",
    )


app = rx.App()
app.add_page(index, title="Rincewrite")
