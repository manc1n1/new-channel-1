from dash import Dash, dcc, html, Input, Output, State, callback
import requests

app = Dash(__name__)

app.layout = html.Div(
    [
        html.Div(
            className="container",
            children=[
                html.H1(id="title", children="News Channel 1"),
            ],
        ),
        html.Div(
            className="content",
            children=[
                dcc.Input(
                    id="location",
                    type="text",
                    placeholder="Type a location",
                    debounce=True,
                ),
                html.Button("Submit", id="submit-btn"),
                html.Div(id="output"),
            ],
        ),
    ]
)


@callback(
    Output("output", "children"),
    Input("location", "value"),
    prevent_initial_call=True,
)
def update_output(location):
    url = "https://geocoding-api.open-meteo.com/v1/search?name={}&count=1&language=en&format=json".format(
        location
    )
    req = requests.get(url).json()
    print(req)


if __name__ == "__main__":
    app.run(debug=True)
