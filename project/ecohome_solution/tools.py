"""
Tools for EcoHome Energy Advisor Agent
"""
import os
import json
import random
from datetime import datetime, timedelta
from typing import Dict, Any
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from models.energy import DatabaseManager

# Initialize database manager
db_manager = DatabaseManager()

# TODO: Implement get_weather_forecast tool
@tool
def get_weather_forecast(location: str, days: int = 3) -> Dict[str, Any]:
    """
    Get weather forecast for a specific location and number of days.
    
    Args:
        location (str): Location to get weather for (e.g., "San Francisco, CA")
        days (int): Number of days to forecast (1-7)
    
    Returns:
        Dict[str, Any]: Weather forecast data including temperature, conditions, and solar irradiance
        E.g:
        forecast = {
            "location": ...,
            "forecast_days": ...,
            "current": {
                "temperature_c": ...,
                "condition": random.choice(["sunny", "partly_cloudy", "cloudy"]),
                "humidity": ...,
                "wind_speed": ...
            },
            "hourly": [
                {
                    "hour": ..., # for hour in range(24)
                    "temperature_c": ...,
                    "condition": ...,
                    "solar_irradiance": ...,
                    "humidity": ...,
                    "wind_speed": ...
                },
            ]
        }
    """
    # Mock weather API or call OpenWeatherMap or similar


    try:
        # Basic validation
        days = max(1, min(int(days), 7))

        # Create a stable seed from location + date (keeps results consistent per day)
        today = datetime.now().date()
        seed_str = f"{location.lower().strip()}::{today.isoformat()}::{days}"
        seed = sum(ord(c) for c in seed_str)
        rng = random.Random(seed)

        # Helper: map condition -> solar multiplier
        def condition_solar_factor(cond: str) -> float:
            return {
                "sunny": 1.00,
                "partly_cloudy": 0.70,
                "cloudy": 0.35,
                "rain": 0.20,
            }.get(cond, 0.60)

        # Helper: approximate solar curve (0 at night, peak midday)
        # hour: 0-23 -> normalized 0..1
        def solar_curve(hour: int) -> float:
            # Daylight window roughly 6..18
            if hour < 6 or hour > 18:
                return 0.0
            # Peak around noon (12)
            # simple triangular curve: 6->0, 12->1, 18->0
            if hour <= 12:
                return (hour - 6) / 6.0
            else:
                return (18 - hour) / 6.0

        # Base climate-ish values (mock)
        base_temp = rng.randint(18, 32)
        base_humidity = rng.randint(35, 75)
        base_wind = round(rng.uniform(1.5, 7.5), 1)

        # Choose a prevailing condition for "current", with some realism
        current_condition = rng.choices(
            population=["sunny", "partly_cloudy", "cloudy", "rain"],
            weights=[45, 35, 15, 5],
            k=1
        )[0]

        # Build a simple multi-day summary + next-24h hourly forecast
        daily = []
        for d in range(days):
            day_date = today + timedelta(days=d)
            # Slight temp drift day-to-day
            drift = rng.randint(-2, 2)
            day_condition = rng.choices(
                population=["sunny", "partly_cloudy", "cloudy", "rain"],
                weights=[45, 35, 15, 5],
                k=1
            )[0]
            daily.append({
                "date": day_date.isoformat(),
                "high_temp_c": base_temp + drift + rng.randint(1, 4),
                "low_temp_c": base_temp + drift - rng.randint(3, 6),
                "condition": day_condition
            })

        # Hourly forecast for next 24 hours (for "today" context)
        hourly = []
        for hour in range(24):
            # Temperature curve: cooler early morning, warmer afternoon
            # peak around 15:00
            # simple curve based on distance from 15
            temp_variation = -abs(hour - 15) * 0.4 + rng.uniform(-0.6, 0.6)
            temp_c = round(base_temp + temp_variation, 1)

            # Condition can vary slightly hour-to-hour but follow prevailing
            # Keep it stable-ish to avoid noisy results
            if hour in (8, 12, 16, 20):
                condition = rng.choices(
                    population=["sunny", "partly_cloudy", "cloudy", "rain"],
                    weights=[45, 35, 15, 5],
                    k=1
                )[0]
            else:
                condition = current_condition

            # Solar irradiance: curve * condition factor + tiny noise
            irradiance = solar_curve(hour) * condition_solar_factor(condition)
            irradiance = max(0.0, min(1.0, irradiance + rng.uniform(-0.05, 0.05)))
            irradiance = round(irradiance, 3)

            humidity = int(max(20, min(90, base_humidity + rng.randint(-8, 8))))
            wind_speed = round(max(0.0, base_wind + rng.uniform(-1.2, 1.2)), 1)

            hourly.append({
                "hour": hour,
                "temperature_c": temp_c,
                "condition": condition,
                "solar_irradiance": irradiance,
                "humidity": humidity,
                "wind_speed": wind_speed
            })

        forecast = {
            "location": location,
            "forecast_days": days,
            "current": {
                "temperature_c": round(base_temp + rng.uniform(-1.5, 1.5), 1),
                "condition": current_condition,
                "humidity": base_humidity,
                "wind_speed": base_wind
            },
            "daily": daily,
            "hourly": hourly
        }

        return forecast

    except Exception as e:
        return {"error": f"Failed to get weather forecast: {str(e)}"}


# TODO: Implement get_electricity_prices tool
@tool
def get_electricity_prices(date: str = None) -> Dict[str, Any]:
    """
    Get electricity prices for a specific date or current day.
    
    Args:
        date (str): Date in YYYY-MM-DD format (defaults to today)
    
    Returns:
        Dict[str, Any]: Electricity pricing data with hourly rates 
        E.g: 
        prices = {
            "date": ...,
            "pricing_type": "time_of_use",
            "currency": "USD",
            "unit": "per_kWh",
            "hourly_rates": [
                {
                    "hour": .., # for hour in range(24)
                    "rate": ..,
                    "period": ..,
                    "demand_charge": ...
                }
            ]
        }
    """
    # Mock electricity pricing - in real implementation, this would call a pricing API
    # Use a base price per kWh    
    # Then generate hourly rates with peak/off-peak pricing
    # Peak normally between 6 and 22...
    # demand_charge should be 0 if off-peak
    try:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Validate/parse date
        day = datetime.strptime(date, "%Y-%m-%d").date()

        # Stable seed per date so pricing doesn't change randomly between runs
        seed_str = f"pricing::{day.isoformat()}"
        seed = sum(ord(c) for c in seed_str)
        rng = random.Random(seed)

        # Base price per kWh (mock)
        base_price = round(rng.uniform(0.10, 0.16), 3)

        # Define time-of-use windows (as per your comment: Peak between 6 and 22)
        # We'll add finer categories for better recommendations:
        # - off_peak: 22-6 (low)
        # - mid_peak: 6-16 and 20-22 (medium)
        # - peak: 16-20 (highest) but still within 6-22
        def rate_for_hour(h: int) -> Dict[str, Any]:
            if h < 6 or h >= 22:
                period = "off_peak"
                multiplier = rng.uniform(0.70, 0.85)
                demand_charge = 0.0
            elif 16 <= h < 20:
                period = "peak"
                multiplier = rng.uniform(1.45, 1.70)
                demand_charge = round(rng.uniform(0.03, 0.08), 3)  # non-zero at peak
            else:
                period = "mid_peak"
                multiplier = rng.uniform(1.00, 1.25)
                demand_charge = round(rng.uniform(0.01, 0.03), 3)  # small non-zero

            rate = round(base_price * multiplier, 3)
            return {"rate": rate, "period": period, "demand_charge": demand_charge}

        hourly_rates = []
        for hour in range(24):
            r = rate_for_hour(hour)
            hourly_rates.append({
                "hour": hour,
                "rate": r["rate"],
                "period": r["period"],
                "demand_charge": r["demand_charge"]
            })

        prices = {
            "date": date,
            "pricing_type": "time_of_use",
            "currency": "USD",
            "unit": "per_kWh",
            "base_rate": base_price,
            "hourly_rates": hourly_rates
        }

        return prices

    except Exception as e:
        return {"error": f"Failed to get electricity prices: {str(e)}"}

@tool
def query_energy_usage(start_date: str, end_date: str, device_type: str = None) -> Dict[str, Any]:
    """
    Query energy usage data from the database for a specific date range.
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        device_type (str): Optional device type filter (e.g., "EV", "HVAC", "appliance")
    
    Returns:
        Dict[str, Any]: Energy usage data with consumption details
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        records = db_manager.get_usage_by_date_range(start_dt, end_dt)
        
        if device_type:
            records = [r for r in records if r.device_type == device_type]
        
        usage_data = {
            "start_date": start_date,
            "end_date": end_date,
            "device_type": device_type,
            "total_records": len(records),
            "total_consumption_kwh": round(sum(r.consumption_kwh for r in records), 2),
            "total_cost_usd": round(sum(r.cost_usd or 0 for r in records), 2),
            "records": []
        }
        
        for record in records:
            usage_data["records"].append({
                "timestamp": record.timestamp.isoformat(),
                "consumption_kwh": record.consumption_kwh,
                "device_type": record.device_type,
                "device_name": record.device_name,
                "cost_usd": record.cost_usd
            })
        
        return usage_data
    except Exception as e:
        return {"error": f"Failed to query energy usage: {str(e)}"}

@tool
def query_solar_generation(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Query solar generation data from the database for a specific date range.
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
    
    Returns:
        Dict[str, Any]: Solar generation data with production details
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        records = db_manager.get_generation_by_date_range(start_dt, end_dt)
        
        generation_data = {
            "start_date": start_date,
            "end_date": end_date,
            "total_records": len(records),
            "total_generation_kwh": round(sum(r.generation_kwh for r in records), 2),
            "average_daily_generation": round(sum(r.generation_kwh for r in records) / max(1, (end_dt - start_dt).days), 2),
            "records": []
        }
        
        for record in records:
            generation_data["records"].append({
                "timestamp": record.timestamp.isoformat(),
                "generation_kwh": record.generation_kwh,
                "weather_condition": record.weather_condition,
                "temperature_c": record.temperature_c,
                "solar_irradiance": record.solar_irradiance
            })
        
        return generation_data
    except Exception as e:
        return {"error": f"Failed to query solar generation: {str(e)}"}

@tool
def get_recent_energy_summary(hours: int = 24) -> Dict[str, Any]:
    """
    Get a summary of recent energy usage and solar generation.
    
    Args:
        hours (int): Number of hours to look back (default 24)
    
    Returns:
        Dict[str, Any]: Summary of recent energy data
    """
    try:
        usage_records = db_manager.get_recent_usage(hours)
        generation_records = db_manager.get_recent_generation(hours)
        
        summary = {
            "time_period_hours": hours,
            "usage": {
                "total_consumption_kwh": round(sum(r.consumption_kwh for r in usage_records), 2),
                "total_cost_usd": round(sum(r.cost_usd or 0 for r in usage_records), 2),
                "device_breakdown": {}
            },
            "generation": {
                "total_generation_kwh": round(sum(r.generation_kwh for r in generation_records), 2),
                "average_weather": "sunny" if generation_records else "unknown"
            }
        }
        
        # Calculate device breakdown
        for record in usage_records:
            device = record.device_type or "unknown"
            if device not in summary["usage"]["device_breakdown"]:
                summary["usage"]["device_breakdown"][device] = {
                    "consumption_kwh": 0,
                    "cost_usd": 0,
                    "records": 0
                }
            summary["usage"]["device_breakdown"][device]["consumption_kwh"] += record.consumption_kwh
            summary["usage"]["device_breakdown"][device]["cost_usd"] += record.cost_usd or 0
            summary["usage"]["device_breakdown"][device]["records"] += 1
        
        # Round the breakdown values
        for device_data in summary["usage"]["device_breakdown"].values():
            device_data["consumption_kwh"] = round(device_data["consumption_kwh"], 2)
            device_data["cost_usd"] = round(device_data["cost_usd"], 2)
        
        return summary
    except Exception as e:
        return {"error": f"Failed to get recent energy summary: {str(e)}"}

@tool
def search_energy_tips(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search for energy-saving tips and best practices using RAG.
    
    Args:
        query (str): Search query for energy tips
        max_results (int): Maximum number of results to return
    
    Returns:
        Dict[str, Any]: Relevant energy tips and best practices
    """
    try:
        # Initialize vector store if it doesn't exist
        persist_directory = "data/vectorstore"
        if not os.path.exists(persist_directory):
            os.makedirs(persist_directory)
        
        # Load documents if vector store doesn't exist
        if not os.path.exists(os.path.join(persist_directory, "chroma.sqlite3")):
            # Load documents
            documents = []
            for doc_path in ["data/documents/tip_device_best_practices.txt", "data/documents/tip_energy_savings.txt"]:
                if os.path.exists(doc_path):
                    loader = TextLoader(doc_path)
                    docs = loader.load()
                    documents.extend(docs)
            
            # Split documents
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = text_splitter.split_documents(documents)
            
            # Create vector store
            embeddings = OpenAIEmbeddings()
            vectorstore = Chroma.from_documents(
                documents=splits,
                embedding=embeddings,
                persist_directory=persist_directory
            )
        else:
            # Load existing vector store
            embeddings = OpenAIEmbeddings()
            vectorstore = Chroma(
                persist_directory=persist_directory,
                embedding_function=embeddings
            )
        
        # Search for relevant documents
        docs = vectorstore.similarity_search(query, k=max_results)
        
        results = {
            "query": query,
            "total_results": len(docs),
            "tips": []
        }
        
        for i, doc in enumerate(docs):
            results["tips"].append({
                "rank": i + 1,
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "relevance_score": "high" if i < 2 else "medium" if i < 4 else "low"
            })
        
        return results
    except Exception as e:
        return {"error": f"Failed to search energy tips: {str(e)}"}

@tool
def calculate_energy_savings(device_type: str, current_usage_kwh: float, 
                           optimized_usage_kwh: float, price_per_kwh: float = 0.12) -> Dict[str, Any]:
    """
    Calculate potential energy savings from optimization.
    
    Args:
        device_type (str): Type of device being optimized
        current_usage_kwh (float): Current energy usage in kWh
        optimized_usage_kwh (float): Optimized energy usage in kWh
        price_per_kwh (float): Price per kWh (default 0.12)
    
    Returns:
        Dict[str, Any]: Savings calculation results
    """
    savings_kwh = current_usage_kwh - optimized_usage_kwh
    savings_usd = savings_kwh * price_per_kwh
    savings_percentage = (savings_kwh / current_usage_kwh) * 100 if current_usage_kwh > 0 else 0
    
    return {
        "device_type": device_type,
        "current_usage_kwh": current_usage_kwh,
        "optimized_usage_kwh": optimized_usage_kwh,
        "savings_kwh": round(savings_kwh, 2),
        "savings_usd": round(savings_usd, 2),
        "savings_percentage": round(savings_percentage, 1),
        "price_per_kwh": price_per_kwh,
        "annual_savings_usd": round(savings_usd * 365, 2)
    }


TOOL_KIT = [
    get_weather_forecast,
    get_electricity_prices,
    query_energy_usage,
    query_solar_generation,
    get_recent_energy_summary,
    search_energy_tips,
    calculate_energy_savings
]
