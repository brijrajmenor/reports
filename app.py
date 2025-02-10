import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import re
import pandas as pd
from datetime import datetime, timedelta

# Initialize Firestore client
# Initialize Firebase if not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate("https://github.com/brijrajmenor/reports/blob/main/login-for-reporting-firebase-adminsdk-fbsvc-951c1cbb2f.json")  # Update this path
    firebase_admin.initialize_app(cred)

# Initialize Firestore client
db = firestore.client()


def authenticate_user(email, password):
    """Authenticate user using Firestore with proper error handling."""

    user_ref = db.collection("users").document(email)
    user_doc = user_ref.get()

    if not user_doc.exists:
        return "invalid"  # Email not found in Firestore

    user_data = user_doc.to_dict()

    if user_data.get("disabled", False):
        return "disabled"  # User account is disabled

    if user_data.get("password") == password:
        return user_data  # Successful login

    return "invalid"  # Incorrect password


# Streamlit app title
st.set_page_config(page_title="Reporting", page_icon="logo.jpg")

# Create a login form
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = authenticate_user(email, password)

        if user == "disabled":
            st.error("This account is disabled. Please contact the administrator.")

        elif user == "invalid":
            st.error("Invalid email or password.")

        else:
            st.session_state.logged_in = True
            st.session_state.user = user  # Store user data in session state
            st.success("Login successful!")

else:
    st.write("Welcome to the reports dashboard!")
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
            off_times = off_events[off_events["Room No"] == room_no].reset_index(
                drop=True
            )

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
