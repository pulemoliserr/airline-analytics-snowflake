"""
AeroPulse: Executive & Operations Intelligence Suite
=====================================================
Role-based airport analytics platform powered by Snowflake BACKFILL schema.
Roles: Executive Director, Ground Operations, Network Planner, Commercial Director.

Run with:
    streamlit run streamlit/app.py
"""

import os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import snowflake.connector
import streamlit as st

# ── Page Configuration ────────────────────────────────────────────────
st.set_page_config(
    page_title="AeroPulse Intelligence Suite",
    page_icon="✈️",
    layout="wide",
)

TEMPLATE = "plotly_white"

# Custom CSS for executive card styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }
    .action-box {
        background-color: #eef2f7;
        border-left: 5px solid #636EFA;
        padding: 12px 15px;
        border-radius: 4px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ── Snowflake Connection ──────────────────────────────────────────────
@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema="BACKFILL",
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        login_timeout=120,
        network_timeout=120,
    )


@st.cache_data(ttl=300)
def run_query(sql: str) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        columns = [desc[0].lower() for desc in cur.description]
        data = cur.fetchall()
        return pd.DataFrame(data, columns=columns)
    finally:
        cur.close()


# ── Data Loaders ──────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_all_data():
    df_airport = run_query("""
        SELECT airport_icao, city, country,
               SUM(total_arrivals) AS arrivals,
               SUM(total_departures) AS departures,
               SUM(total_movements) AS total_movements,
               ROUND(AVG(total_movements), 0) AS avg_daily,
               MIN(flight_date) AS data_from,
               MAX(flight_date) AS data_to,
               COUNT(DISTINCT flight_date) AS days
        FROM gld_daily_airport_traffic
        GROUP BY 1, 2, 3
        ORDER BY total_movements DESC
    """)
    df_daily = run_query("""
        SELECT flight_date, airport_icao, city, total_arrivals, total_departures, total_movements
        FROM gld_daily_airport_traffic
        ORDER BY flight_date, airport_icao
    """)
    df_hourly = run_query("""
        SELECT airport_icao, city, departure_hour_local,
               SUM(flight_count) AS flights
        FROM gld_hourly_flight_activity
        GROUP BY 1, 2, 3
        ORDER BY 1, 3
    """)
    df_airline = run_query("""
        SELECT airport_icao, city, airline_name, alliance,
               SUM(total_flights) AS flights,
               COUNT(DISTINCT unique_aircraft) AS unique_aircraft
        FROM gld_airline_traffic
        WHERE airline_name IS NOT NULL
        GROUP BY 1, 2, 3, 4
        ORDER BY airport_icao, flights DESC
    """)
    df_routes = run_query("""
        SELECT departure_airport_icao, arrival_airport_icao,
               departure_city, arrival_city,
               total_flights,
               ROUND(avg_duration_min, 0) AS avg_duration_min,
               unique_aircraft, days_with_service
        FROM gld_route_analysis
        ORDER BY total_flights DESC
    """)
    return df_airport, df_daily, df_hourly, df_airline, df_routes


airport_df, daily_df, hourly_df, airline_df, routes_df = load_all_data()

# ── Global Sidebar Control ────────────────────────────────────────────
st.sidebar.title("✈️ AeroPulse Control")
st.sidebar.markdown("---")

airport_options = airport_df["airport_icao"].tolist()
city_map = dict(zip(airport_df["airport_icao"], airport_df["city"]))
country_map = dict(zip(airport_df["airport_icao"], airport_df["country"]))

selected = st.sidebar.selectbox(
    "Select Operating Hub",
    options=airport_options,
    format_func=lambda x: f"{x} — {city_map[x]} ({country_map[x]})",
)

my = airport_df[airport_df["airport_icao"] == selected].iloc[0]
peers = airport_df[airport_df["airport_icao"] != selected]

st.sidebar.markdown("---")
st.sidebar.info(
    f"**Active Hub:** {city_map[selected]} ({selected})\n\n"
    f"**Reporting Period:** {my['data_from']} to {my['data_to']}\n\n"
    f"**Data Source:** OpenSky Network via Snowflake BACKFILL"
)

# ── Main Header ───────────────────────────────────────────────────────
st.title(f"AeroPulse: {city_map[selected]} ({selected}) Intelligence Hub")
st.caption(
    f"Multi-Role Strategic Dashboard | Evaluated across {int(my['days'])} days of clean telemetry"
)

# ── Multi-Role Tabs ───────────────────────────────────────────────────
tab_exec, tab_ground, tab_network, tab_commercial = st.tabs([
    "👔 Executive Dashboard & Actions",
    "⚡ Gate & Ground Operations",
    "🗺️ Route Network & Expansion",
    "🤝 Commercial & Airline Risk"
])


# =====================================================================
# TAB 1: EXECUTIVE DASHBOARD & ACTION POINTS
# =====================================================================
with tab_exec:
    st.subheader("Executive KPI Scorecard")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("7-Day Total Movements", f"{int(my['total_movements']):,}")
    col2.metric("Daily Average Volume", f"{int(my['avg_daily']):,}")
    
    # Peer Rank Calculation
    rank = int((airport_df["avg_daily"] >= my["avg_daily"]).sum())
    col3.metric("Global Hub Rank", f"#{rank} of 6", delta=f"Avg: {int(peers['avg_daily'].mean())}")
    
    imbalance = int(my["departures"]) - int(my["arrivals"])
    imbalance_pct = round(imbalance * 100 / my["total_movements"], 1) if my["total_movements"] > 0 else 0
    col4.metric("Turnaround Skew", f"{imbalance_pct:+.1f}%", delta=f"{imbalance:+d} flights", delta_color="off")

    st.divider()
    st.subheader("🚨 Automated Executive Action Register")
    st.markdown("Dynamic recommendations generated from telemetry anomalies and operational thresholds:")

    actions_triggered = 0

    # Action 1: Imbalance check
    if abs(imbalance_pct) > 3.0:
        actions_triggered += 1
        skew_direction = "Departures" if imbalance > 0 else "Arrivals"
        st.markdown(f"""
        <div class="action-box">
            <strong>Action Item #{actions_triggered} (Operations & Fleet):</strong> 
            {city_map[selected]} exhibits a <strong>{abs(imbalance_pct)}% skew toward {skew_direction}</strong>. 
            <em>Recommendation:</em> Coordinate with ground handlers for equipment repositioning and evaluate dynamic gate turnaround slots.
        </div>
        """, unsafe_allow_html=True)

    # Action 2: Peak Congestion Check
    my_hourly = hourly_df[hourly_df["airport_icao"] == selected].copy()
    if not my_hourly.empty:
        peak_flights = my_hourly["flights"].max()
        congested_hours = len(my_hourly[my_hourly["flights"] >= peak_flights * 0.85])
        if congested_hours >= 4:
            actions_triggered += 1
            st.markdown(f"""
            <div class="action-box">
                <strong>Action Item #{actions_triggered} (Capacity & Slot Management):</strong> 
                Identified <strong>{congested_hours} hours</strong> operating at >=85% of peak capacity. 
                <em>Recommendation:</em> Implement peak-hour congestion pricing or off-peak slot incentives to smooth runway demand.
            </div>
            """, unsafe_allow_html=True)

    # Action 3: Airline Concentration Risk Check
    my_airlines = airline_df[airline_df["airport_icao"] == selected].copy()
    if not my_airlines.empty:
        total_airline_flights = my_airlines["flights"].sum()
        top1_share = round(my_airlines["flights"].iloc[0] * 100 / total_airline_flights, 1)
        if top1_share > 30.0:
            actions_triggered += 1
            top_carrier = my_airlines["airline_name"].iloc[0]
            st.markdown(f"""
            <div class="action-box">
                <strong>Action Item #{actions_triggered} (Commercial Risk):</strong> 
                Dominant carrier <strong>{top_carrier}</strong> holds <strong>{top1_share}%</strong> market share. 
                <em>Recommendation:</em> Establish strategic route development funds to attract competing carriers and reduce single-airline dependency risk.
            </div>
            """, unsafe_allow_html=True)

    if actions_triggered == 0:
        st.success("All operational and commercial indices are within normal optimal operating boundaries. No urgent corrective actions required.")


# =====================================================================
# TAB 2: GATE & GROUND OPERATIONS (OPERATIONS MANAGER)
# =====================================================================
with tab_ground:
    st.subheader("Hourly Pressure & Peak Congestion Analysis")
    st.markdown("Local time distribution of flights to support ground crew roster optimization and gate assignments.")

    my_hourly = hourly_df[hourly_df["airport_icao"] == selected].copy()

    if not my_hourly.empty:
        peak_row = my_hourly.loc[my_hourly["flights"].idxmax()]
        peak_local_hr = int(peak_row["departure_hour_local"])
        peak_vol = int(peak_row["flights"])

        col_left, col_right = st.columns([3, 2])

        with col_left:
            fig_hourly = go.Figure(go.Bar(
                x=my_hourly["departure_hour_local"],
                y=my_hourly["flights"],
                marker_color=["#EF553B" if f >= peak_vol * 0.85 else "#636EFA" for f in my_hourly["flights"]],
                hovertemplate="Hour: %{x}:00<br>Flights: %{y}<extra></extra>"
            ))
            fig_hourly.update_layout(
                template=TEMPLATE,
                xaxis_title="Local Departure Hour",
                yaxis_title="Total Movements (7 Days)",
                xaxis=dict(dtick=1),
                height=380,
                margin=dict(t=10)
            )
            st.plotly_chart(fig_hourly, use_container_width=True)

        with col_right:
            st.markdown("##### Ground Operations Summary")
            st.markdown(f"""
            * **Peak Hour:** {peak_local_hr:02d}:00 local time
            * **Peak Volume:** {peak_vol} movements
            * **Congestion Threshold:** {int(peak_vol * 0.85)} flights/hr
            """)
            
            quiet_hours = my_hourly[my_hourly["flights"] < peak_vol * 0.3]["departure_hour_local"].tolist()
            quiet_str = ", ".join(f"{int(h):02d}:00" for h in sorted(quiet_hours)) if quiet_hours else "None"
            st.markdown(f"* **Maintenance / Low-Traffic Windows:** {quiet_str}")
            
            st.info("💡 **Ground Staffing Tip:** Schedule shift rotations 1 hour prior to peak volume onset to ensure full gate apron readiness.")


# =====================================================================
# TAB 3: ROUTE NETWORK & EXPANSION (NETWORK PLANNER)
# =====================================================================
with tab_network:
    st.subheader("Top Route Connectivity & Duration Profile")
    st.markdown("Analysis of high-frequency corridors connected to this hub.")

    my_routes = routes_df[
        (routes_df["departure_airport_icao"] == selected) |
        (routes_df["arrival_airport_icao"] == selected)
    ].head(10).copy()

    if not my_routes.empty:
        my_routes["route"] = my_routes["departure_city"] + " → " + my_routes["arrival_city"]

        fig_routes = px.bar(
            my_routes.sort_values("total_flights", ascending=True),
            x="total_flights",
            y="route",
            orientation="h",
            color="avg_duration_min",
            color_continuous_scale="Blues",
            labels={"total_flights": "Total Flights", "route": "", "avg_duration_min": "Avg Duration (min)"},
            template=TEMPLATE,
        )
        fig_routes.update_layout(height=420, margin=dict(t=10))
        st.plotly_chart(fig_routes, use_container_width=True)

        st.markdown("##### Route Portfolio Breakdown")
        col_m1, col_m2 = st.columns(2)
        total_routes_count = len(routes_df[(routes_df["departure_airport_icao"] == selected) | (routes_df["arrival_airport_icao"] == selected)])
        unique_dest_count = len(set(routes_df[routes_df["departure_airport_icao"] == selected]["arrival_airport_icao"].tolist()))
        
        col_m1.metric("Tracked Active Routes", total_routes_count)
        col_m2.metric("Unique Connected Destinations", unique_dest_count)
    else:
        st.warning("No route data recorded for this hub during the backfill period.")


# =====================================================================
# TAB 4: COMMERCIAL & AIRLINE RISK (COMMERCIAL DIRECTOR)
# =====================================================================
with tab_commercial:
    st.subheader("Carrier Market Share & Alliance Distribution")
    st.markdown("Evaluating airline dependency, alliance presence, and market concentration risk (HHI Index).")

    my_airlines = airline_df[airline_df["airport_icao"] == selected].copy()

    if not my_airlines.empty:
        total_flights = my_airlines["flights"].sum()
        my_airlines["share_pct"] = round(my_airlines["flights"] * 100 / total_flights, 1)
        top5 = my_airlines.head(5)

        col_p1, col_p2 = st.columns([2, 3])

        with col_p1:
            others_flights = total_flights - top5["flights"].sum()
            others_share = round(100 - top5["share_pct"].sum(), 1)
            
            pie_df = pd.concat([
                top5[["airline_name", "flights", "share_pct"]],
                pd.DataFrame({"airline_name": ["Others"], "flights": [others_flights], "share_pct": [others_share]})
            ], ignore_index=True)

            fig_pie = px.pie(
                pie_df, values="flights", names="airline_name", hole=0.4, template=TEMPLATE
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            fig_pie.update_layout(height=360, margin=dict(t=10, b=10), showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_p2:
            st.markdown("##### Top Carriers Table")
            display_df = top5[["airline_name", "alliance", "flights", "share_pct", "unique_aircraft"]].rename(
                columns={
                    "airline_name": "Airline",
                    "alliance": "Alliance",
                    "flights": "Flights",
                    "share_pct": "Market Share %",
                    "unique_aircraft": "Distinct Aircraft"
                }
            )
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            # HHI Calculation
            hhi = int((my_airlines["share_pct"] ** 2).sum())
            st.markdown(f"**Herfindahl-Hirschman Index (HHI):** `{hhi}`")
            if hhi > 2500:
                st.caption("🔴 Highly Concentrated Market (High single-airline vulnerability)")
            elif hhi > 1500:
                st.caption("🟡 Moderately Concentrated Market")
            else:
                st.caption("🟢 Competitive Market Structure")
    else:
        st.warning("No airline traffic data available for this airport.")

# ── Footer ────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "AeroPulse Executive Intelligence Suite | "
    "Architecture: Apache Airflow → Snowflake → dbt → Streamlit | "
    "Confidential — Internal Airport Operations Use Only"
)