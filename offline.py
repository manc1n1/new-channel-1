from dash import Dash, dcc, html, Input, Output, callback, html
from dash.exceptions import PreventUpdate
from retry_requests import retry
import dash_leaflet as dl
import dash_daq as daq
import datetime as dt
from datetime import timedelta
import numpy as np
import openmeteo_requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import requests_cache
import sqlite3
from urllib.parse import urlparse, parse_qs


data = pd.read_csv("./db.csv")

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect("weather_data.db")

# Write the data to SQLite
data.to_sql("weather", conn, if_exists="replace", index=False)

query = "SELECT * FROM weather"
df = pd.read_sql_query(query, conn)


colorscale = ["black", "lightblue", "blue", "green", "yellow", "red", "white"]

app = Dash(__name__)


def get_local_time(df):
    # Prepare the API request
    # url = "https://api.open-meteo.com/v1/forecast"
    # params = {
    #     "latitude": latitude,
    #     "longitude": longitude,
    #     "current_weather": True,
    #     "timezone": "auto",
    # }

    # Send the request to Open-Meteo
    # response = requests.get(url, params=params)
    # data = response.json()

    # Print the full JSON response to inspect its structure
    # print("API Response:", data)

    try:
        df["local_time"] = pd.to_datetime(df["time"], format="%Y-%m-%dT%H:%M")

        # Adjust for the timezone offset
        df["local_time"] = df.apply(
            lambda row: row["local_time"],
            axis=1,
        )

        return df["local_time"]
    except KeyError as e:
        return f"KeyError - {str(e)}: Check your data structure."


def degrees_to_direction(degrees):
    if degrees < 0 or degrees > 360:
        return "Invalid degree input. Degrees must be between 0 and 360."

    # Normalize degrees to be within 0-360
    degrees = degrees % 360

    if (degrees >= 0 and degrees < 22.5) or (degrees >= 337.5 and degrees <= 360):
        return "North"
    elif degrees >= 22.5 and degrees < 67.5:
        return "Northeast"
    elif degrees >= 67.5 and degrees < 112.5:
        return "East"
    elif degrees >= 112.5 and degrees < 157.5:
        return "Southeast"
    elif degrees >= 157.5 and degrees < 202.5:
        return "South"
    elif degrees >= 202.5 and degrees < 247.5:
        return "Southwest"
    elif degrees >= 247.5 and degrees < 292.5:
        return "West"
    elif degrees >= 292.5 and degrees < 337.5:
        return "Northwest"
    else:
        return "Unknown Direction"


def wind_direction_arrow(direction_degrees, length=1):
    # Convert degrees to radians for trigonometric calculations
    direction_radians = np.deg2rad(direction_degrees)

    # Calculate arrow components
    dx = length * np.sin(direction_radians)
    dy = length * np.cos(direction_radians)

    # Create a plotly figure
    fig = go.Figure()

    # Add an arrow using annotations
    fig.add_annotation(
        x=0,
        y=0,
        ax=dx,
        ay=dy,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=2,
        arrowsize=1,
        arrowwidth=2,
        arrowcolor="#f38ba8",
    )

    # Set plot limits and layout options
    fig.update_xaxes(range=[-1.5, 1.5], showgrid=False, zeroline=False, visible=False)
    fig.update_yaxes(range=[-1.5, 1.5], showgrid=False, zeroline=False, visible=False)

    fig.update_layout(
        title={
            "text": f"Wind Direction: {degrees_to_direction(direction_degrees)}",
            "x": 0.5,
            "y": 1,
            "xanchor": "center",
            "yanchor": "top",
        },
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font=dict(family="sans-serif", color="#89b4fa"),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False),
        width=400,
        height=400,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )

    return fig


def format_12hr(time_str):
    # Extract hours and minutes
    hour, minute = map(int, time_str.split(":"))
    # Apply modulo 12 to get the hour in 12-hour format
    hour_12 = hour % 12
    # Adjust hour from '0' to '12' for 12 AM and 12 PM
    hour_12 = 12 if hour_12 == 0 else hour_12
    # Determine AM/PM
    am_pm = "AM" if hour < 12 else "PM"
    # Return formatted time
    return f"{hour_12}:{minute:02d} {am_pm}"


app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        html.Div(
            className="container",
            children=[
                html.H1(id="title", children="Weather Dashboard"),
            ],
        ),
        html.Div(
            className="content",
            children=[
                # dcc.Input(
                #     id="location",
                #     type="text",
                #     placeholder="City or ZIP Code",
                #     value="",
                #     debounce=True,
                # ),
                # html.Button("Submit", id="submit-btn"),
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
                                # dl.WMSTileLayer(
                                #     url="https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0r.cgi",
                                #     layers="nexrad-n0r-900913",
                                #     format="image/png",
                                #     transparent=True,
                                # ),
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
                        html.Div(id="precip-thermometer"),
                        html.Div(id="thermometer"),
                        html.Div(id="compass"),
                    ],
                ),
                html.Div(
                    style={"display": "flex", "justifyContent": "space-around"},
                    children=[
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
        Output("precip-thermometer", "children"),
        Output("thermometer", "children"),
        Output("compass", "children"),
        Output("time-series-chart", "children"),
    ],
    [
        Input("url", "pathname"),
        Input("url", "search"),
    ],
    prevent_initial_call=True,
)
def update_output(pathname, search):
    # Here you can parse the pathname or search to extract your parameters
    # Example, URL could be: http://127.0.0.1:8050/page?location=NewYork
    query_params = parse_qs(urlparse(search).query)
    index_str = query_params.get("index", ["0"])[0]  # Default to None if not set
    try:
        # Convert index to integer
        index = int(index_str)
        lat = df["latitude"][index]
        lon = df["longitude"][index]
        # geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
        # res = requests.get(geocode_url).json()
        # lat = df["latitude"][index]
        # lon = df["longitude"][index]

        # now = dt.datetime.now(dt.timezone.utc)

        new_center = [lat, lon]
        new_position = [lat, lon]

        popup_content = [
            html.Div(
                [
                    html.Span("Date/Time: ", style={"fontWeight": "bold"}),
                    html.Span(f"{pd.to_datetime(df['time'][index])}"),
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
        # forecast_url = "https://api.open-meteo.com/v1/forecast"
        # params = {
        #     "latitude": lat,
        #     "longitude": lon,
        #     "hourly": [
        #         "temperature_2m",
        #         "relative_humidity_2m",
        #         "precipitation_probability",
        #         "wind_speed_10m",
        #         "wind_direction_10m",
        #     ],
        #     "temperature_unit": "fahrenheit",
        #     "wind_speed_unit": "mph",
        #     "precipitation_unit": "inch",
        #     "timezone": "auto",
        #     "forecast_days": 1,
        # }
        # responses = openmeteo.weather_api(forecast_url, params=params)

        # Process first location. Add a for-loop for multiple locations or weather models
        # response = responses[0]
        popup_content.append(
            html.Div(
                [
                    html.Span("Elevation: ", style={"fontWeight": "bold"}),
                    html.Span(f"{df['elevation'][index]}m asl"),
                ]
            ),
        )

        # Process hourly data. The order of variables needs to be the same as requested.
        # hourly = response.Hourly()
        # hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
        # hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
        # hourly_precipitation_probability = hourly.Variables(2).ValuesAsNumpy()
        # hourly_wind_speed_10m = hourly.Variables(3).ValuesAsNumpy()
        # hourly_wind_direction_10m = hourly.Variables(4).ValuesAsNumpy()

        # hourly_data = {
        #     "date": pd.date_range(
        #         start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        #         end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        #         freq=pd.Timedelta(seconds=hourly.Interval()),
        #         inclusive="left",
        #     )
        # }
        # hourly_data["temperature_2m"] = hourly_temperature_2m
        # hourly_data["relative_humidity_2m"] = hourly_relative_humidity_2m
        # hourly_data["precipitation_probability"] = hourly_precipitation_probability
        # hourly_data["wind_speed_10m"] = hourly_wind_speed_10m
        # hourly_data["wind_direction_10m"] = hourly_wind_direction_10m

        # hourly_dataframe = pd.DataFrame(data=hourly_data)

        # print(hourly_dataframe)

        # current_hour_data = hourly_dataframe.loc[
        #     (hourly_dataframe["date"].dt.hour == now.hour)
        #     & (hourly_dataframe["date"].dt.date == now.date())
        # ]

        # print(current_hour_data)

        humidity_gauge = daq.Gauge(
            color={
                "gradient": True,
                "ranges": {
                    "#a6e3a1": [0, 33],
                    "#f9e2af": [33, 66],
                    "#f38ba8": [66, 100],
                },
            },
            showCurrentValue=True,
            value=df["relative_humidity_2m"][index],
            label="Humidity (%)",
            max=100,
            min=0,
        )

        precip_thermometer = daq.Thermometer(
            height=140,
            min=0,
            max=1,
            value=df["precipitation"][index],
            showCurrentValue=True,
            color="#89b4fa",
            label="Precipitation (inches)",
        )

        thermometer = daq.Thermometer(
            height=140,
            min=-50,
            max=135,
            value=df["temperature_2m"][index],
            showCurrentValue=True,
            color="#f38ba8",
            label="Temperature (ºF)",
        )

        compass = dcc.Graph(
            figure=wind_direction_arrow(df["wind_direction_10m"][index])
        )

        local_times = get_local_time(df)

        current_local_time = local_times.iloc[index]

        # Convert to the format expected by Plotly (milliseconds since the Unix epoch)
        current_time_ms = int(current_local_time.timestamp() * 1000)

        # print(current_hour_data["wind_speed_10m"].values[0])

        fig = px.line(
            df,
            x="time",
            y="wind_speed_10m",
        )
        fig.update_traces(
            line=dict(color="#89b4fa"),
            hovertemplate="Time: %{x|%Y-%m-%d %H:%M}<br>Wind Speed: %{y:.2f} mph",
        )
        fig.update_layout(
            title="Wind Speed vs. Time",
            title_x=0.5,
            xaxis_title=f"Time",
            yaxis_title="Wind Speed (mph)",
            xaxis=dict(
                title_font=dict(size=14),
                tickfont=dict(size=12),
            ),
            yaxis=dict(
                title_font=dict(size=14),
                tickfont=dict(size=12),
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            font=dict(family="sans-serif", color="#89b4fa"),
            width=1200,
            height=500,
            margin={"l": 20, "r": 20, "t": 50, "b": 20},
        )
        fig.add_vline(
            x=current_time_ms,
            line_width=5,
            line_dash="dash",
            line_color="#f38ba8",
            annotation_text=f"  Current Time",
            annotation_position="top right",
            annotation_font=dict(
                color="#f38ba8",  # Set the color of the annotation text
                size=12,  # Optionally set the size of the text
            ),
            xref="x",
        )
        fig.update_xaxes(type="date")
        wind_speed_fig = dcc.Graph(figure=fig)

        popup_content.append(
            html.Div(
                [
                    html.Span("Temperature: ", style={"fontWeight": "bold"}),
                    html.Span(f"{df['temperature_2m'][index]}ºF"),
                ]
            ),
        )
        popup_content.append(
            html.Div(
                [
                    html.Span("Precip. Probability: ", style={"fontWeight": "bold"}),
                    html.Span(f"{df['precipitation'][index]} inches"),
                ]
            ),
        )

        return (
            new_center,
            new_position,
            popup_content,
            new_style,
            humidity_gauge,
            precip_thermometer,
            thermometer,
            compass,
            wind_speed_fig,
        )
    except ValueError:
        print(f"Invalid index value: {index_str}")
    except KeyError:
        print(f"Index out of bounds: {index}")
    except IndexError:
        print(f"Index out of bounds: {index}")


conn.close()

if __name__ == "__main__":
    app.run(debug=True)
