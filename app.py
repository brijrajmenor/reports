import pandas as pd
from datetime import timedelta
import streamlit as st
import re  # Import regex
import plotly.express as px
import plotly.graph_objects as go

# Streamlit app title
st.set_page_config("Reporting", page_icon="logo.jpg")
st.title("Netcreators Automation")
st.title("Smart Room Controller Reports")
st.markdown(
    """
        Upload the .txt file, select the date and time, and generate the summary report for the day.
        Follow the instructions as given below, to use the app.
    """
)

# File uploader
uploaded_file = st.file_uploader("Upload your log file", type=["txt"])

if uploaded_file is not None:
    # Load the data from the uploaded text file
    log_data = uploaded_file.readlines()

    # Extract relevant entries from the log data
    events = []
    for line in log_data:
        line = line.decode("utf-8")  # Decode bytes to string

        # Regex to ensure space between 'Room no.' and the room number
        line = re.sub(r"(Room no\.)(\d+)", r"\1 \2", line)

        if "light is ON" in line or "light is OFF" in line:
            # Split the line to extract timestamp and event details
            parts = line.split("\t")
            timestamp = parts[0].strip()
            room_info = parts[1].strip()

            # Extract room number and light status
            room_no = room_info.split(" ")[2]
            light_status = "ON" if "ON" in room_info else "OFF"

            # Append to the events list
            events.append((timestamp, room_no, light_status))

    # Create a DataFrame from the events
    df = pd.DataFrame(events, columns=["Timestamp", "Room No", "Light Status"])

    # Convert Timestamp to datetime
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%Y-%m-%d %p %I:%M")

    # Date filter inputs in Streamlit
    st.sidebar.header("Filter Options")

    # Select a date range
    start_date = st.sidebar.date_input(
        "Start date", value=pd.to_datetime(df["Timestamp"].min()).date()
    )
    end_date = st.sidebar.date_input(
        "End date", value=pd.to_datetime(df["Timestamp"].max()).date()
    )

    # Optionally select time range
    filter_time = st.sidebar.checkbox("Filter by time range")
    if filter_time:
        start_time = st.sidebar.time_input(
            "Start time", value=pd.Timestamp("00:00:00").time()
        )
        end_time = st.sidebar.time_input(
            "End time", value=pd.Timestamp("23:59:59").time()
        )
    else:
        start_time = pd.Timestamp("00:00:00").time()
        end_time = pd.Timestamp("23:59:59").time()

    # Combine selected date and time into datetime
    start_datetime = pd.Timestamp.combine(start_date, start_time)
    end_datetime = pd.Timestamp.combine(end_date, end_time)

    # Filter the data based on selected date and time range
    df_filtered = df[
        (df["Timestamp"] >= start_datetime) & (df["Timestamp"] <= end_datetime)
    ]

    # ** Add Room Number Filter **
    room_options = df_filtered["Room No"].unique()
    selected_rooms = st.sidebar.multiselect(
        "Select Room Numbers", room_options, room_options
    )

    # Filter the data based on selected rooms
    df_filtered = df_filtered[df_filtered["Room No"].isin(selected_rooms)]

    # Separate ON and OFF events after filtering
    on_events = df_filtered[df_filtered["Light Status"] == "ON"]
    off_events = df_filtered[df_filtered["Light Status"] == "OFF"]

    # Clean up the data by ensuring that each ON event is paired with the nearest subsequent OFF event
    cleaned_summary = []

    for room_no in df_filtered["Room No"].unique():
        # Filter ON and OFF events for this room
        on_times = on_events[on_events["Room No"] == room_no].reset_index(drop=True)
        off_times = off_events[off_events["Room No"] == room_no].reset_index(drop=True)

        # Match ON and OFF events only if ON comes before OFF
        i, j = 0, 0
        while i < len(on_times) and j < len(off_times):
            on_time = on_times.loc[i, "Timestamp"]
            off_time = off_times.loc[j, "Timestamp"]

            if on_time < off_time:
                # Calculate duration
                duration_minutes = (
                    off_time - on_time
                ).total_seconds() / 60  # duration in minutes
                duration_timedelta = timedelta(minutes=duration_minutes)

                # Convert to days, hours, minutes
                days = duration_timedelta.days
                hours, minutes = divmod(duration_timedelta.seconds // 60, 60)
                duration_str = f"{days}d {hours}h {minutes}m"

                # Mark durations less than 15 minutes as Housekeeping
                if duration_minutes < 15:
                    label = "Housekeeping"
                else:
                    label = "Guest"

                # Append the valid ON-OFF pair and duration
                cleaned_summary.append(
                    (room_no, on_time, off_time, duration_str, label)
                )
                i += 1
                j += 1
            else:
                j += 1

    # Create a cleaned summary DataFrame
    cleaned_summary_df = pd.DataFrame(
        cleaned_summary,
        columns=["Room No", "Light ON", "Light OFF", "Duration", "Label"],
    )

    # Filter out durations of 1 minute or less
    filtered_summary_df = cleaned_summary_df[
        cleaned_summary_df["Duration"] != "0d 0h 1m"
    ].reset_index(drop=True)

    # ** Add Occupancy Filter **
    occupancy_options = ["Guest", "Housekeeping"]
    selected_occupancy = st.sidebar.multiselect(
        "Select Occupancy Type", occupancy_options, occupancy_options
    )

    # Filter the data based on selected occupancy type
    filtered_summary_df = filtered_summary_df[
        filtered_summary_df["Label"].isin(selected_occupancy)
    ]

    # Display the cleaned summary DataFrame in Streamlit
    st.write("Filtered and Cleaned Summary Data")
    st.dataframe(filtered_summary_df)

    # Generate dynamic file name based on date range
    file_name = f"room_summary_{start_date}_to_{end_date}.xlsx".replace(":", "-")

    # Option to download the cleaned data
    if st.button("Download cleaned data as Excel"):
        output_file_path = file_name
        filtered_summary_df.to_excel(output_file_path, index=False)

        with open(output_file_path, "rb") as file:
            btn = st.download_button(
                label="Download Excel",
                data=file,
                file_name=output_file_path,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # Date-wise Light ON/OFF Count (Bar Chart)
    if not filtered_summary_df.empty:
        filtered_summary_df["Date"] = filtered_summary_df["Light ON"].dt.date
        light_status_count_by_date = (
            filtered_summary_df.groupby(["Date", "Label"])
            .size()
            .reset_index(name="Count")
        )

        light_status_plot = px.bar(
            light_status_count_by_date,
            x="Date",
            y="Count",
            color="Label",
            barmode="group",
            title="Date-wise Light ON/OFF Count",
            labels={"Date": "Date", "Count": "Event Count"},
        )
        st.plotly_chart(light_status_plot)

    # Date-wise Average Duration of Light ON (Line Chart)
    if not filtered_summary_df.empty:
        filtered_summary_df["Date"] = filtered_summary_df["Light ON"].dt.date
        filtered_summary_df["Duration (minutes)"] = filtered_summary_df[
            "Duration"
        ].apply(
            lambda x: int(x.split("d")[0]) * 1440
            + int(x.split("d")[1].split("h")[0]) * 60
            + int(x.split("h")[1].split("m")[0])
        )
        avg_duration_by_date = (
            filtered_summary_df.groupby("Date")["Duration (minutes)"]
            .mean()
            .reset_index()
        )

        avg_duration_plot = px.line(
            avg_duration_by_date,
            x="Date",
            y="Duration (minutes)",
            title="Date-wise Average Duration of Light ON",
            labels={"Date": "Date", "Duration (minutes)": "Average Duration (minutes)"},
        )
        st.plotly_chart(avg_duration_plot)
