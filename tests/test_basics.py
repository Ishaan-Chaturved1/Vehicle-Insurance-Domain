import pytest
from src.constants import PIPELINE_NAME, ARTIFACT_DIR, TARGET_COLUMN
from src.pipline.prediction_pipeline import VehicleData


def test_constants():
    assert PIPELINE_NAME == "vehicle_insurance"
    assert ARTIFACT_DIR == "artifact"
    assert TARGET_COLUMN == "Response"


def test_vehicle_data_to_dataframe():
    data = VehicleData(
        Gender="Male",
        Age=25,
        Driving_License=1,
        Region_Code=28.0,
        Previously_Insured=0,
        Annual_Premium=35000.0,
        Policy_Sales_Channel=152.0,
        Vintage=150,
        Vehicle_Age="< 1 Year",
        Vehicle_Damage="Yes",
    )
    df = data.get_vehicle_input_data_frame()
    assert not df.empty
    assert df.shape[0] == 1
    assert "Age" in df.columns
    assert df["Age"].iloc[0] == 25


def test_fastapi_app_instance():
    from app import app
    assert app is not None
    assert app.title == "FastAPI"

