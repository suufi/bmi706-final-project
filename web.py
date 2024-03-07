import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from vega_datasets import data

alt.data_transformers.enable("data_server")


@st.cache_data
def load_data():
    ihme_data = pd.read_csv("IHME-GBD_2019_DATA-03e0c24f-1.csv")
    ihme_data = ihme_data[ihme_data["year"].between(2000, 2019)]

    water_data = pd.read_excel("JMP_2023_WLD.xlsx", sheet_name="wat")
    san_data = pd.read_excel("JMP_2023_WLD.xlsx", sheet_name="san")

    country_code_mappings = pd.read_json(
        "https://raw.githubusercontent.com/alisle/world-110m-country-codes/master/world-110m-country-codes.json"
    )

    # replace country names
    country_code_mappings["name"] = country_code_mappings["name"].replace(
        {
            "Bolivia, Plurinational State of": "Bolivia (Plurinational State of)",
            "Congo, the Democratic Republic of the": "Democratic Republic of the Congo",
            "Cote d'Ivoire": "Côte d'Ivoire",
            "Czech Republic": "Czechia",
            "Iran, Islamic Republic of": "Iran (Islamic Republic of)",
            "Korea, Democratic People's Republic of": "Democratic People's Republic of Korea",
            "Korea, Republic of": "Republic of Korea",
            "Macedonia, the former Yugoslav Republic of": "North Macedonia",
            "Moldova, Republic of": "Republic of Moldova",
            "Swaziland": "Eswatini",
            "Taiwan, Province of China": "Taiwan (Province of China)",
            "Tanzania, United Republic of": "United Republic of Tanzania",
            "United States": "United States of America",
            "Venezuela, Bolivarian Republic of": "Venezuela (Bolivarian Republic of)",
        }
    )

    water_data["name"] = water_data["name"].replace(
        {"Türkiye": "Turkey", "Netherlands (Kingdom of the)": "Netherlands"}
    )
    san_data["name"] = san_data["name"].replace(
        {"Türkiye": "Turkey", "Netherlands (Kingdom of the)": "Netherlands"}
    )

    country_code_mappings.rename(columns={"id": "iso_id"}, inplace=True)
    # merge location_name from ihme_data with name in country_code_mappings
    ihme_data = ihme_data.merge(
        country_code_mappings, left_on="location_name", right_on="name"
    )

    ihme_data = ihme_data.pivot(
        index=["iso_id", "location_name", "year", "cause_name", "metric_name"],
        columns="measure_name",
        values="val",
    ).reset_index()

    skin_diseases = (
        ihme_data[
            ihme_data["cause_name"].isin(
                [
                    "Bacterial skin diseases",
                    "Viral skin diseases",
                    "Fungal skin diseases",
                ]
            )
        ]
        .groupby(["iso_id", "location_name", "year", "metric_name"])
        .sum()
    )
    skin_diseases["cause_name"] = "Skin diseases"
    skin_diseases.reset_index(inplace=True)

    ihme_data = ihme_data[
        ~ihme_data["cause_name"].isin(
            ["Bacterial skin diseases", "Viral skin diseases", "Fungal skin diseases"]
        )
    ]

    ihme_data = pd.concat([ihme_data, skin_diseases])

    ihme_data.head()

    merged_data = pd.merge(
        ihme_data,
        water_data,
        left_on=["location_name", "year"],
        right_on=["name", "year"],
        how="left",
    )

    merged_data = pd.merge(
        merged_data,
        san_data,
        left_on=["location_name", "year"],
        right_on=["name", "year"],
        how="left",
    )

    merged_data.rename(
        columns={
            "wat_sm_t": "Water - Safely Managed %",
            "san_sm_t": "Sanitation - Safely Managed %",
        },
        inplace=True,
    )

    return merged_data


df = load_data()

st.write("# Water & Sanitation + Deaths")

st.write("## Global View")
st.write("Select a year, cause of death, and metric to view the data.")
st.write("Rate is the number of deaths per 100,000 people.")

year = st.slider(
    "Year",
    min_value=np.min(df["year"].astype(int)),
    max_value=np.max(df["year"].astype(int)),
    value=2014,
)
subset = df[df["year"] == year]

cause_of_death = st.selectbox(
    "Cause of Death",
    options=subset["cause_name"].unique(),
    index=0,
)
subset = subset[subset["cause_name"] == cause_of_death]

metric = st.selectbox(
    "Metric Format",
    options=["Number", "Percent", "Rate"],
    index=2,
)
subset = subset[subset["metric_name"] == metric]

measure = st.selectbox(
    "Measure", options=["DALYs (Disability-Adjusted Life Years)", "Deaths"], index=1
)

world = alt.topo_feature(data.world_110m.url, "countries")

country_selection = alt.selection_single(
    fields=["location_name"], empty="all", on="click"
)
country_binding = alt.condition(
    country_selection,
    alt.Color("location_name:N", legend=None),
    alt.value("lightgray"),
)

base_map = (
    alt.Chart(world)
    .mark_geoshape(
        fill="lightgray",
        stroke="white",
    )
    .properties(width=800, height=400)
    .project("naturalEarth1")
    .interactive()
    .add_selection(country_selection)
)

map = base_map.encode(
    fill=(
        measure == "Deaths"
        and alt.Color("Deaths:Q", scale=alt.Scale(scheme="reds"))
        or alt.Color(
            "DALYs (Disability-Adjusted Life Years):Q",
            scale=alt.Scale(scheme="reds"),
        )
    ),
    tooltip=[
        "location_name:N",
        "Deaths:Q",
        "DALYs (Disability-Adjusted Life Years):Q",
        "Population:Q",
    ],
).transform_lookup(
    lookup="id",
    from_=alt.LookupData(
        subset,
        "iso_id",
        [
            "location_name",
            "Deaths",
            "DALYs (Disability-Adjusted Life Years)",
            "pop_t_x",
        ],
    ),
    as_=[
        "location_name",
        "Deaths",
        "DALYs (Disability-Adjusted Life Years)",
        "Population",
    ],
)

st.altair_chart(map, use_container_width=True)

safety_selection = st.selectbox(
    "Select a safety measure",
    options=["Water - Safely Managed %", "Sanitation - Safely Managed %"],
    index=0,
)

map2 = (
    base_map.encode(
        fill=(
            safety_selection == "Water - Safely Managed %"
            and alt.Color(
                "Water - Safely Managed %:Q",
                scale=alt.Scale(scheme="greens"),
                title="Water",
            )
            or alt.Color(
                "Sanitation - Safely Managed %:Q",
                scale=alt.Scale(scheme="oranges"),
                title="Sanitation",
            )
        ),
        tooltip=[
            "location_name:N",
            alt.Tooltip(
                "Water - Safely Managed %:Q",
                title="Water Safely Managed %",
            ),
            alt.Tooltip(
                "Sanitation - Safely Managed %:Q",
                title="Sanitation Safely Managed %",
            ),
        ],
    )
    .transform_lookup(
        lookup="id",
        from_=alt.LookupData(
            subset,
            "iso_id",
            [
                "location_name",
                "Water - Safely Managed %",
                "Sanitation - Safely Managed %",
            ],
        ),
        as_=[
            "location_name",
            "Water - Safely Managed %",
            "Sanitation - Safely Managed %",
        ],
    )
    .transform_filter(country_selection)
)


st.altair_chart(map2, use_container_width=True)

st.write(f"## Country-Level Data")
# select a country
country_selection = st.selectbox(
    "Select a country", options=subset["location_name"].unique(), index=0
)

country_data = df[df["location_name"] == country_selection]
country_data = country_data[country_data["metric_name"] == metric]
country_data = country_data[country_data["cause_name"] == cause_of_death]


base = alt.Chart(country_data).encode(x="year:O")

daly_death_chart = (
    base.mark_line(point=True)
    .encode(
        x="year:O",
        y=alt.Y(
            measure == "Deaths"
            and "Deaths:Q"
            or "DALYs (Disability-Adjusted Life Years):Q",
            title=f"{measure} ({metric})",
        ),
    )
    .properties(
        title=f"{cause_of_death} {metric} for {country_selection}",
    )
)

safety_chart_base = base.mark_line(point=True).encode(
    x="year:O",
    y=alt.Y(
        "Water - Safely Managed %:Q",
        title="Safely Managed % (Total)",
    ),
)
safety_chart = safety_chart_base.mark_line(point=True).encode(
    y=alt.Y(
        "Water - Safely Managed %:Q",
    ),
    color=alt.value("green"),
) + safety_chart_base.mark_line(point=True).encode(
    y=alt.Y(
        "Sanitation - Safely Managed %:Q",
    ),
    color=alt.value("orange"),
)

st.altair_chart(daly_death_chart, use_container_width=True)
st.altair_chart(safety_chart, use_container_width=True)
