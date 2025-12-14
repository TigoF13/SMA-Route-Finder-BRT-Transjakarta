# SMA-Based Route Finder for Transjakarta BRT Network
This project is a Django-based web application developed as part of an undergraduate thesis.
It implements the Slime Mould Algorithm (SMA) to determine optimal routes on the Transjakarta Bus Rapid Transit (BRT) network, based on spatial data and user-defined routing preferences.

## Description

This application aims to model and analyze route-finding problems on the Transjakarta BRT network using a metaheuristic approach, specifically the Slime Mould Algorithm (SMA).

The Transjakarta corridor network is represented as a graph derived from GeoJSON spatial data, where nodes and edges correspond to BRT stops and corridor segments. The SMA algorithm is applied to explore and exploit possible routes between origin and destination points, considering multiple optimization preferences such as distance, number of transfers, and route efficiency.

The system was developed to support experimental evaluation in an academic context, allowing comparison of routing results under different preference scenarios.

## Getting Started

### Dependencies

The project was developed and tested using the following environment:
* Operating System: Windows 10 / Windows 11
* Programming Language: Python 3.9+
* Framework: Django 4.x
* Main Libraries: 
    * Django
    * NumPy
    * Pandas
    * GeoPandas
    * NetworkX
    * Shapely
    * Matplotlib

## Installing
### 1. Clone the repository
```
git clone https://github.com/TigoF13/SMA-Route-Finder-BRT-Transjakarta.git
cd SMA-Route-Finder-BRT-Transjakarta
```

### 2. Create and activate virtual environment
```
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies
```
pip install -r requirements.txt
```

### 4. Database setup
```
python manage.py migrate
```

## Executing Program
To run the application locally:
### 1. Start Django development server
```
py manage.py runserver
```

### 2. Access the application
Open your browser and go to:
```
http://127.0.0.1:8000/
```

### 3. Routing Evaluation
Experimental results generated during thesis evaluation are stored in:
```
evaluation_log_skripsi.xlsx
```

