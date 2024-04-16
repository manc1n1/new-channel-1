from dash import Dash, dcc, html, Input, Output, callback
from dash.exceptions import PreventUpdate
from retry_requests import retry
import dash_leaflet as dl
import dash_daq as daq
import datetime as dt
import openmeteo_requests
import pandas as pd
import requests
import requests_cache
import plotly.express as px


colorscale = ["black", "lightblue", "blue", "green", "yellow", "red", "white"]

app = Dash(__name__)

app.layout = html.Div(
    [
        html.Div(
            className="container",
            children=[
                html.H1(id="title", children="Weather Dashboard"),
            ],
        ),
        html.Div(
            className="content",
            children=[
                dcc.Input(
                    id="location",
                    type="text",
                    placeholder="City or ZIP Code",
                    value="",
                    debounce=True,
                ),
                html.Button("Submit", id="submit-btn"),
                html.Div(
                    style={"visibility": "hidden"},
                    id="map-container",
                    children=[
                        dl.Map(
                            id="map",
                            children=[
                                dl.TileLayer(),
                                dl.Colorbar(
                                    colorscale=colorscale,
                                    width=20,
                                    height=200,
                                    nTicks=5,
                                    min=0,
                                    max=75,
                                    unit="dBZ",
                                    position="topright",
                                ),
                                dl.Marker(
                                    id="marker",
                                    children=[dl.Popup(id="pop-up")],
                                    position=[0, 0],
                                ),
                                dl.WMSTileLayer(
                                    url="https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0r.cgi",
                                    layers="nexrad-n0r-900913",
                                    format="image/png",
                                    transparent=True,
                                ),
                            ],
                            center=[0, 0],
                            zoom=8,
                            style={"height": "50vh"},
                        ),
                    ],
                ),
                html.Div(
                    style={"display": "flex", "justifyContent": "space-around"},
                    children=[
                        html.Div(id="humidity-gauge"),
                        html.Div(id="thermometer"),
                        html.Div(id="time-series-chart"),
                    ],
                ),
            ],
        ),
    ]
)


@callback(
    [
        Output("map", "center"),
        Output("marker", "position"),
        Output("pop-up", "children"),
        Output("map-container", "style"),
        Output("humidity-gauge", "children"),
        Output("thermometer", "children"),
        Output("time-series-chart", "children"),
    ],
    Input("location", "value"),
    prevent_initial_call=True,

)
def update_output(location):
    if not location:
        raise PreventUpdate

    geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
    res = requests.get(geocode_url).json()
    lat = res["results"][0]["latitude"]
    lon = res["results"][0]["longitude"]

    now = dt.datetime.now(dt.timezone.utc)

    new_center = [lat, lon]
    new_position = [lat, lon]
    popup_content = [
        html.Div(
            [
                html.Span("Location: ", style={"fontWeight": "bold"}),
                html.Span(
                    f"{res['results'][0]['name']}, {res['results'][0]['admin1']}, {res['results'][0]['country']}"
                ),
            ]
        ),
        html.Div(
            [
                html.Span("Coordinates: ", style={"fontWeight": "bold"}),
                html.Span(f"{lat}°, {lon}°"),
            ]
        ),
    ]
    new_style = {
        "visibility": "visible",
    }

    # Setup the Open-Meteo API client with cache and retry on error
    cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    # Make sure all required weather variables are listed here
    # The order of variables in hourly or daily is important to assign them correctly below
    forecast_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation_probability",
            "wind_speed_10m",
            "wind_direction_10m",
        ],
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
        "forecast_days": 1,
    }
    responses = openmeteo.weather_api(forecast_url, params=params)

    # Process first location. Add a for-loop for multiple locations or weather models
    response = responses[0]
    popup_content.append(
        html.Div(
            [
                html.Span("Elevation: ", style={"fontWeight": "bold"}),
                html.Span(f"{response.Elevation()}m asl"),
            ]
        ),
    )

    # Process hourly data. The order of variables needs to be the same as requested.
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
    hourly_precipitation_probability = hourly.Variables(2).ValuesAsNumpy()
    hourly_wind_speed_10m = hourly.Variables(3).ValuesAsNumpy()
    hourly_wind_direction_10m = hourly.Variables(4).ValuesAsNumpy()

    hourly_data = {
        "date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left",
        )
    }
    hourly_data["temperature_2m"] = hourly_temperature_2m
    hourly_data["relative_humidity_2m"] = hourly_relative_humidity_2m
    hourly_data["precipitation_probability"] = hourly_precipitation_probability
    hourly_data["wind_speed_10m"] = hourly_wind_speed_10m
    hourly_data["wind_direction_10m"] = hourly_wind_direction_10m

    hourly_dataframe = pd.DataFrame(data=hourly_data)

    print(hourly_dataframe)

    current_hour_data = hourly_dataframe.loc[
        (hourly_dataframe["date"].dt.hour == now.hour)
        & (hourly_dataframe["date"].dt.date == now.date())
    ]

    humidity_gauge = daq.Gauge(
        color={
            "gradient": True,
            "ranges": {"#a6e3a1": [0, 33], "#f9e2af": [33, 66], "#f38ba8": [66, 100]},
        },
        showCurrentValue=True,
        value=current_hour_data["relative_humidity_2m"].values[0],
        label="Humidity (%)",
        max=100,
        min=0,
    )

    thermometer = daq.Thermometer(
        height=160,
        min=-50,
        max=135,
        value=current_hour_data["temperature_2m"].values[0],
        showCurrentValue=True,
        color="#f38ba8",
        label="Temperature (ºF)",
    )

    fig = px.line(hourly_dataframe, x='date', y='wind_speed_10m')
    fig.update_layout(
        title="Wind Speed",
        title_x=0.5,
        xaxis_title="Time",
        yaxis_title="Wind Speed (mph)",
        xaxis=dict(
            tickformat="%H:%M",
            title_font=dict(size=14),
            tickfont=dict(size=12),
        ),
        yaxis=dict(
            title_font=dict(size=14),
            tickfont=dict(size=12),
        ),
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="rgba(0,0,0,0.3)", 
        font=dict(family="Arial, sans-serif", size=12, color="#FFF"),
        height=400,
        width=600,
        margin=dict(l=50, r=50, t=50, b=50),
    )

    wind_speed_fig = dcc.Graph(figure=fig)

    popup_content.append(
        html.Div(
            [
                html.Span("Temperature: ", style={"fontWeight": "bold"}),
                html.Span(f"{current_hour_data['temperature_2m'].values[0]}ºF"),
            ]
        ),
    )
    popup_content.append(
        html.Div(
            [
                html.Span("Precip. Probability: ", style={"fontWeight": "bold"}),
                html.Span(
                    f"{current_hour_data['precipitation_probability'].values[0]}%"
                ),
            ]
        ),
    )

    return (
        new_center,
        new_position,
        popup_content,
        new_style,
        humidity_gauge,
        thermometer,
        wind_speed_fig,
    )


if __name__ == "__main__":
    app.run(debug=True)
