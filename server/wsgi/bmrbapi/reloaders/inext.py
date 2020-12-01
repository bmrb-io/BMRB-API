#!/usr/bin/env python3

import logging
import os

import pandas as pd
import psycopg2
import psycopg2.extras

from bmrbapi.utils.connections import PostgresConnection


def inext() -> None:
    inext_folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), "iNext")

    conn = PostgresConnection(write_access=True)
    with conn as cur:
        # Prepare the averages table
        cur.execute("DROP TABLE IF EXISTS web.inext_data;")
        cur.execute("""
CREATE TABLE web.inext_data
(
    id          SERIAL PRIMARY KEY,
    index       INT,
    status      TEXT,
    sum_formula TEXT,
    mass        TEXT,
    purity      TEXT,
    smiles      TEXT,
    position    TEXT,
    spectrum    TEXT,
    barcode     TEXT,
    binding     TEXT
);""")

        # Load all the iNext spreadsheets
        for file in os.listdir(inext_folder):
            path = os.path.join(inext_folder, file)
            if not os.path.isfile(path):
                continue
            logging.info(f'Working on iNext file {file}')

            # Load the file on sheet at a time
            for sheet in range(1, 9):
                logging.info(f'Working on sheet {sheet}')
                df = pd.read_excel(path, sheet_name=f"Plate{sheet}")
                df = df.rename(columns={
                    "Index": "index",
                    "Status": "status",
                    "Sum Formula": "sum_formula",
                    "Mass": "mass",
                    "Purity": "purity",
                    "SMILES Formula": "smiles",
                    "Position": "position",
                    "Spectrum": "spectrum",
                    "Barcode": "barcode",
                    "Binding/Non-Binding": "binding"
                })
                del df['Structure']

                # Create a list of tuples from the dataframe values
                tuples = [tuple(x) for x in df.to_numpy()]
                # Comma-separated dataframe columns
                cols = ','.join(list(df.columns))
                # SQL query to execute
                query = f"INSERT INTO web.inext_data ({cols}) VALUES %s"

                try:
                    psycopg2.extras.execute_values(cur, query, tuples)
                except (Exception, psycopg2.DatabaseError) as error:
                    logging.exception("Error: %s", error)
                    conn.rollback()
                    raise error

        conn.commit()
