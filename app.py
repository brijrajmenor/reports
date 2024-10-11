import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
from io import BytesIO


# Step 1: Process the data and calculate time spent
def process_data(lines, start_datetime, end_datetime):
    data = []
    last_on_time = {}

    for line in lines:
        if not line.strip():  # Skip empty lines
            continue

        parts = line.strip().split("\t")
        timestamp_str = parts[0]

        # Try parsing the datetime with the correct format
        try:
            event_datetime = datetime.strptime(timestamp_str, "%Y-%m-%d %p %I:%M")
            print("Event date: ", event_datetime)
            print("Time Stamp: ", timestamp_str)
            print("Start Date time: ", start_datetime)
        except ValueError:
            print(f"Skipping invalid timestamp: {timestamp_str}")  # Log the error
            continue  # Skip this line if parsing fails

        # Apply date/time filters
        if not (start_datetime <= event_datetime <= end_datetime):
            continue  # Skip if outside of selected range

        if "light is ON" in line:
            room = parts[1].split(" ")[2]  # Extract room number
            last_on_time[room] = event_datetime
            data.append(
                {
                    "Timestamp": timestamp_str,
                    "Room": room,
                    "Status": "on",
                    "Time Spent": None,
                }
            )

        elif "light is OFF" in line:
            room = parts[1].split(" ")[2]
            off_time = event_datetime

            if room in last_on_time:
                time_spent = off_time - last_on_time[room]

                # Update the last 'on' event with the time spent
                for record in data:
                    if (
                        record["Room"] == room
                        and record["Status"] == "on"
                        and record["Time Spent"] is None
                    ):
                        record["Time Spent"] = time_spent
                        break

                data.append(
                    {
                        "Timestamp": timestamp_str,
                        "Room": room,
                        "Status": "off",
                        "Time Spent": None,
                    }
                )
                last_on_time.pop(room)

    return data


# Step 2: Generate Summary Report
def generate_summary(data):
    summary = []

    for record in data:
        if record["Status"] == "on" and record["Time Spent"] is not None:
            # Extract information for the summary report
            light_on_time = record["Timestamp"]
            room = record["Room"]
            light_off_time = None
            total_time_spent = record["Time Spent"]

            # Find corresponding OFF event
            for off_record in data:
                if off_record["Room"] == room and off_record["Status"] == "off":
                    light_off_time = off_record["Timestamp"]
                    break

            # Append to summary if we have both ON and OFF events
            if light_off_time:
                summary.append(
                    {
                        "Room No": room,
                        "Light On": light_on_time,
                        "Light Off": light_off_time,
                        "Total Time Spent": str(total_time_spent),
                    }
                )

    # Sort summary by Light On timestamp
    summary_sorted = sorted(
        summary, key=lambda x: datetime.strptime(x["Light On"], "%Y-%m-%d %p %I:%M")
    )
    return summary_sorted


# Step 3: Convert data into a DataFrame
def create_dataframe(data):
    df = pd.DataFrame(data)
    return df


# Step 4: Export to Excel and provide download option
def export_to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine="openpyxl")
    df.to_excel(writer, index=False)
    writer.close()
    processed_data = output.getvalue()
    return processed_data


# Streamlit App
def main():
    st.set_page_config(page_title="Reporting")
    st.title("Reports")

    # Step 5: Upload the file
    uploaded_file = st.file_uploader("Choose your input file", type=["txt"])

    if uploaded_file is not None:
        lines = uploaded_file.readlines()
        lines = [line.decode("utf-8") for line in lines]  # Decode to string

        # Step 6: Date range selection
        st.subheader("Select Date Range")
        from_date = st.date_input("From Date", value=datetime.today().date())
        to_date = st.date_input("To Date", value=datetime.today().date())

        # Step 7: Time range selection
        st.subheader("Select Time Range")
        from_time = st.time_input("From Time", value=time(0, 0))
        to_time = st.time_input("To Time", value=time(23, 59))

        # Combine date and time into datetime objects
        start_datetime = datetime.combine(from_date, from_time)
        print("main start time", start_datetime)
        end_datetime = datetime.combine(to_date, to_time)

        # Process data with filtering based on the date/time range
        data = process_data(lines, start_datetime, end_datetime)
        df = create_dataframe(data)

        # Display the DataFrame
        # st.dataframe(df)

        # Generate and display the summary report
        summary = generate_summary(data)
        if summary:
            summary_df = create_dataframe(summary)
            st.subheader("Summary Report")
            st.dataframe(summary_df)

            # Export summary to Excel and download
            summary_excel_data = export_to_excel(summary_df)
            st.download_button(
                label="Download Summary Excel file",
                data=summary_excel_data,
                file_name="switch_summary_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


if __name__ == "__main__":
    main()
