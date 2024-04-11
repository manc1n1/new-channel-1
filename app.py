from dash import Dash, html
import requests

app = Dash(__name__)

app.layout = html.Div(children=[html.H1(id="title", children="News Channel 1")])

location = ""
url = "https://geocoding-api.open-meteo.com/v1/search?name={}&count=1&language=en&format=json".format(
    location
)


if __name__ == "__main__":
    app.run(debug=True)
