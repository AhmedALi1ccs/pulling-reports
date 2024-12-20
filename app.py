import streamlit as st
import http.client
import json
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import re
from io import BytesIO
from datetime import datetime
import math  # Importing math for ceiling function

# Set up the Streamlit app
st.title("Campaign KPI Report")

# Date input for start and end date
start_date = st.date_input("Select the Start Date", value=datetime(2024, 8, 5))
end_date = st.date_input("Select the End Date", value=datetime(2024, 8, 11))

# Campaign input: allow the user to manually add campaign names
manual_campaign = st.text_input("Manually Add Campaign Name (optional)")

# Campaigns dropdown selection (multiselect)
campaigns = [
    "SG", "SG/NEW", "SG5TO10/NEW", "SG1TO5", "SG4/SG7", "SG1TO5/SG5", "SG5TO10",
    "SG4/NEW", "SG5/NEW", "SG4", "SG5", "SG_GST", "SG3", "SG6"
]

# If a manual campaign is added, append it to the list
if manual_campaign:
    campaigns.append(manual_campaign)

selected_campaigns = st.multiselect("Select Campaigns", campaigns, default=campaigns)

# Button to generate report
if st.button('Generate KPI Report'):
    # Establish a secure connection to the server
    conn = http.client.HTTPSConnection("res-summary-app.azurewebsites.net")

    # Define the payload with the selected parameters
    payload = json.dumps({
        "CampaignNames": selected_campaigns,
        "StartDate": start_date.strftime("%Y-%m-%d"),
        "EndDate": end_date.strftime("%Y-%m-%d")
    })

    # Define headers including the authorization token
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer your_token_here'
    }

    # Send a POST request
    conn.request("POST", "/api/alerting/client-weekly-summary", payload, headers)

    # Get the response from the server
    res = conn.getresponse()
    data = res.read()
    response_data = data.decode("utf-8")
    conn.close()

    # Check if the response status is 200 (OK)
    if res.status != 200:
        st.error(f"Error: Received status code {res.status}")
    else:
        # Parse the response JSON data
        parsed_data = json.loads(response_data)

        # Convert the parsed data into a pandas DataFrame
        rows = []
        for campaign, metrics in parsed_data.items():
            category_percentages = metrics.get('categoryPercetnages', {})
            row = {
                'Campaign': campaign,
                'Calls': math.ceil(metrics.get('calls', 0)),
                'Machines': math.ceil(metrics.get('machines', 0)),
                'Connects': math.ceil(metrics.get('connects', 0)),
                'Leads': math.ceil(metrics.get('leads', 0)),
                'Calls to Connects Ratio': math.ceil(metrics.get('callsToConnectsRatio', 0)),
                'Answered Percentage': math.ceil(metrics.get('answeredPercentage', 0)),
                'Not Interested': math.ceil(category_percentages.get('NOT INTERESTED', 0)),
                'Do Not Call': math.ceil(category_percentages.get('DO NOT CALL', 0)),
                'Wrong Number': math.ceil(category_percentages.get('WRONG NUMBER', 0)),
                'Dead Call': math.ceil(category_percentages.get('DEAD CALL', 0)),
                'Voicemail': math.ceil(category_percentages.get('VOICEMAIL', 0)),
                'Not Available': math.ceil(category_percentages.get('NOT AVAILABLE', 0)),
                'Spanish Speaker': math.ceil(category_percentages.get('SPANISH SPEAKER', 0)),
                'Callback': math.ceil(category_percentages.get('CALLBACK', 0)),
            }
            rows.append(row)

        df = pd.DataFrame(rows)

        # Display the DataFrame in the app
        st.dataframe(df)

        # Initialize PDF report buffer
        pdf_buffer = BytesIO()

        # Set up the PDF document
        pdf_file = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        elements = []

        # Set up styles
        styles = getSampleStyleSheet()

        # Add the title for the report, including the date range
        report_title = f"Campaign KPI Report from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        title = Paragraph(report_title, styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Loop through each campaign and generate its section
        for index, row in df.iterrows():
            campaign_name = row['Campaign']
            
            # Sanitize campaign name for filenames (remove/replace invalid characters)
            sanitized_campaign_name = re.sub(r'[^\w\-_\. ]', '_', campaign_name)
            
            # Add campaign title
            elements.append(Paragraph(f"Campaign: <b>{campaign_name}</b>", styles['Heading2']))
            
            # Extract the data for the campaign
            kpi_data = {
                "Machines": math.ceil(row['Machines']),
                "Connects": math.ceil(row['Connects']),
                "Leads": math.ceil(row['Leads']),
                "Calls to Connects Ratio": math.ceil(row['Calls to Connects Ratio']),
                "Answered Percentage": math.ceil(row['Answered Percentage']),
                "Not Interested": math.ceil(row['Not Interested']),
                "Do Not Call": math.ceil(row['Do Not Call']),
                "Wrong Number": math.ceil(row['Wrong Number']),
                "Dead Call": math.ceil(row['Dead Call']),
                "Voicemail": math.ceil(row['Voicemail']),
                "Not Available": math.ceil(row['Not Available']),
                "Spanish Speaker": math.ceil(row['Spanish Speaker']),
                "Callback": math.ceil(row['Callback'])
            }
            
            # Total number of calls for this campaign
            total_calls = row['Calls']
            
            # Check if total_calls is 0
            if total_calls == 0:
                elements.append(Paragraph(f"No calls recorded for campaign: {campaign_name}", styles['Normal']))
                elements.append(Spacer(1, 12))
                continue  # Skip this campaign if no calls were made

            # Prepare data for the bar chart
            outcomes_labels = list(kpi_data.keys())
            outcomes_values = list(kpi_data.values())
            outcomes_values = [0 if pd.isna(value) else value for value in outcomes_values]
            percentages = [(value / total_calls) * 100 for value in outcomes_values]
            
            # Create the bar chart
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.bar(outcomes_labels, percentages, color='skyblue')
            ax.set_xlabel('Metrics')
            ax.set_ylabel('Percentage of Total Calls')
            ax.set_title(f"Call Outcomes for {campaign_name}")
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()

            # Save the chart to a buffer
            img_buffer = BytesIO()
            plt.savefig(img_buffer, format='png')
            img_buffer.seek(0)
            plt.close()

            # Add the bar chart to the report
            elements.append(Image(img_buffer, width=6*inch, height=4*inch))
            elements.append(Spacer(1, 12))
            
            # Create a table with all campaign data (rounded values)
            data = [
                ["Metric", "Value", "Percentage"],
                ["Calls", math.ceil(row['Calls']), "100%"],
                ["Machines", math.ceil(row['Machines']), f"{(row['Machines'] / total_calls) * 100:.2f}%"],
                ["Connects", math.ceil(row['Connects']), f"{(row['Connects'] / total_calls) * 100:.2f}%"],
                ["Leads", math.ceil(row['Leads']), f"{(row['Leads'] / total_calls) * 100:.2f}%"],
                ["Calls to Connects Ratio", math.ceil(row['Calls to Connects Ratio']), "-"],  # Not a percentage
                ["Answered Percentage", math.ceil(row['Answered Percentage']), "-"],  # Not a percentage
                ["Not Interested", math.ceil(row['Not Interested']), f"{(row['Not Interested'] / total_calls) * 100:.2f}%"],
                ["Do Not Call", math.ceil(row['Do Not Call']), f"{(row['Do Not Call'] / total_calls) * 100:.2f}%"],
                ["Wrong Number", math.ceil(row['Wrong Number']), f"{(row['Wrong Number'] / total_calls) * 100:.2f}%"],
                ["Dead Call", math.ceil(row['Dead Call']), f"{(row['Dead Call'] / total_calls) * 100:.2f}%"],
                ["Voicemail", math.ceil(row['Voicemail']), f"{(row['Voicemail'] / total_calls) * 100:.2f}%"],
                ["Not Available", math.ceil(row['Not Available']), f"{(row['Not Available'] / total_calls) * 100:.2f}%"],
                ["Spanish Speaker", math.ceil(row['Spanish Speaker']), f"{(row['Spanish Speaker'] / total_calls) * 100:.2f}%"],
                ["Callback", math.ceil(row['Callback']), f"{(row['Callback'] / total_calls) * 100:.2f}%"]
            ]
            
            table = Table(data, colWidths=[2 * inch, 2 * inch, 2 * inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 12))

        # Summing up the totals for each KPI across all campaigns
        total_row = {
            'Campaign': 'Total',
            'Calls': df['Calls'].sum(),
            'Machines': df['Machines'].sum(),
            'Connects': df['Connects'].sum(),
            'Leads': df['Leads'].sum(),
            'Calls to Connects Ratio': df['Calls to Connects Ratio'].sum(),
            'Answered Percentage': df['Answered Percentage'].sum(),
            'Not Interested': df['Not Interested'].sum(),
            'Do Not Call': df['Do Not Call'].sum(),
            'Wrong Number': df['Wrong Number'].sum(),
            'Dead Call': df['Dead Call'].sum(),
            'Voicemail': df['Voicemail'].sum(),
            'Not Available': df['Not Available'].sum(),
            'Spanish Speaker': df['Spanish Speaker'].sum(),
            'Callback': df['Callback'].sum()
        }

        # Append the total row to the DataFrame
        df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

        # Add total summary to the PDF
        elements.append(Paragraph(f"<b>Total Report for All Campaigns</b>", styles['Heading2']))
        elements.append(Spacer(1, 12))

        # Prepare data for the bar chart for total summary
        outcomes_labels = [
            'Machines', 'Connects', 'Leads', 'Calls to Connects Ratio', 'Answered Percentage', 
            'Not Interested', 'Do Not Call', 'Wrong Number', 'Dead Call', 'Voicemail', 
            'Not Available', 'Spanish Speaker', 'Callback'
        ]
        outcomes_values = [total_row[label] for label in outcomes_labels]
        total_calls = total_row['Calls']

        if total_calls > 0:
            percentages = [(value / total_calls) * 100 for value in outcomes_values]
            
            # Create the bar chart for totals
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.bar(outcomes_labels, percentages, color='lightcoral')
            ax.set_xlabel('Metrics')
            ax.set_ylabel('Percentage of Total Calls')
            ax.set_title('Total Call Outcomes for All Campaigns')
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()

            # Save the chart to a buffer
            total_img_buffer = BytesIO()
            plt.savefig(total_img_buffer, format='png')
            total_img_buffer.seek(0)
            plt.close()

            # Add the total bar chart to the report
            elements.append(Image(total_img_buffer, width=6*inch, height=4*inch))
            elements.append(Spacer(1, 12))

        # Create a table with total campaign data (rounded values)
        total_data = [
            ["Metric", "Value", "Percentage"],
            ["Calls", math.ceil(total_row['Calls']), "100%"],
            ["Machines", math.ceil(total_row['Machines']), f"{(total_row['Machines'] / total_calls) * 100:.2f}%"],
            ["Connects", math.ceil(total_row['Connects']), f"{(total_row['Connects'] / total_calls) * 100:.2f}%"],
            ["Leads", math.ceil(total_row['Leads']), f"{(total_row['Leads'] / total_calls) * 100:.2f}%"],
            ["Calls to Connects Ratio", math.ceil(total_row['Calls to Connects Ratio']), "-"],  # Not a percentage
            ["Answered Percentage", math.ceil(total_row['Answered Percentage']), "-"],  # Not a percentage
            ["Not Interested", math.ceil(total_row['Not Interested']), f"{(total_row['Not Interested'] / total_calls) * 100:.2f}%"],
            ["Do Not Call", math.ceil(total_row['Do Not Call']), f"{(total_row['Do Not Call'] / total_calls) * 100:.2f}%"],
            ["Wrong Number", math.ceil(total_row['Wrong Number']), f"{(total_row['Wrong Number'] / total_calls) * 100:.2f}%"],
            ["Dead Call", math.ceil(total_row['Dead Call']), f"{(total_row['Dead Call'] / total_calls) * 100:.2f}%"],
            ["Voicemail", math.ceil(total_row['Voicemail']), f"{(total_row['Voicemail'] / total_calls) * 100:.2f}%"],
            ["Not Available", math.ceil(total_row['Not Available']), f"{(total_row['Not Available'] / total_calls) * 100:.2f}%"],
            ["Spanish Speaker", math.ceil(total_row['Spanish Speaker']), f"{(total_row['Spanish Speaker'] / total_calls) * 100:.2f}%"],
            ["Callback", math.ceil(total_row['Callback']), f"{(total_row['Callback'] / total_calls) * 100:.2f}%"]
        ]

        # Create the total summary table
        total_table = Table(total_data, colWidths=[2 * inch, 2 * inch, 2 * inch])
        total_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(total_table)
        elements.append(Spacer(1, 12))

        # Build the PDF with the total summary
        pdf_file.build(elements)

        # Custom filename including the date range
        pdf_filename = f"KPI_Report_From_{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}.pdf"

        # Provide download button for the generated PDF report
        st.download_button(
            label="Download KPI Report",
            data=pdf_buffer,
            file_name=pdf_filename,
            mime="application/pdf"
        )
