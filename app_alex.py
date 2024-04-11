from dash import Dash, dcc, html, Input, Output, State, callback
import dash_leaflet as dl
import requests

custom_icon = dict(
    iconUrl='https://leafletjs.com/examples/custom-icons/leaf-green.png',
    shadowUrl='https://leafletjs.com/examples/custom-icons/leaf-shadow.png',
    iconSize=[38, 95],
    shadowSize=[50, 64],
    iconAnchor=[22, 94],
    shadowAnchor=[4, 62],
    popupAnchor=[-3, -76]
)


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
        dl.Map([
            dl.TileLayer(),
            dl.Marker(position=[55, 10]),
            dl.Marker(position=[57, 10], icon=custom_icon),
        ], center=[56,10], zoom=6, style={'height': '50vh'})
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
