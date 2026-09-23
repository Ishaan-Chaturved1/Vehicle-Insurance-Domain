
from src.entity.config_entity import ModelEvaluationConfig
from src.entity.artifact_entity import (
    ModelTrainerArtifact,
    DataIngestionArtifact,
    ModelEvaluationArtifact
)
from sklearn.metrics import f1_score
from src.exception import MyException
from src.constants import TARGET_COLUMN
from src.logger import logging
from src.utils.main_utils import load_object
from src.entity.s3_estimator import Proj1Estimator

import sys
import os
import pandas as pd
from typing import Optional
from dataclasses import dataclass


@dataclass
class EvaluateModelResponse:
    trained_model_f1_score: float
    best_model_f1_score: Optional[float]
    is_model_accepted: bool
    difference: float


class ModelEvaluation:

    def __init__(
        self,
        model_eval_config: ModelEvaluationConfig,
        data_ingestion_artifact: DataIngestionArtifact,
        model_trainer_artifact: ModelTrainerArtifact
    ):
        try:
            self.model_eval_config = model_eval_config
            self.data_ingestion_artifact = data_ingestion_artifact
            self.model_trainer_artifact = model_trainer_artifact

        except Exception as e:
            raise MyException(e, sys) from e

    def get_best_model(self) -> Optional[Proj1Estimator]:
        """
        Method Name : get_best_model

        Description :
            Gets the existing production model from S3 if it exists.

        Output :
            Returns Proj1Estimator if a model exists in S3.
            Returns None if no production model exists.

        On Failure :
            Raises MyException.
        """

        try:
            logging.info("Checking for existing production model in S3.")

            bucket_name = self.model_eval_config.bucket_name
            model_path = self.model_eval_config.s3_model_key_path

            logging.info(
                f"Checking S3 bucket: {bucket_name}, model path: {model_path}"
            )

            # Create S3 estimator.
            # boto3 will automatically use credentials configured
            # through AWS CLI / environment / IAM role.
            proj1_estimator = Proj1Estimator(
                bucket_name=bucket_name,
                model_path=model_path
            )

            # Check whether the model exists in S3.
            if proj1_estimator.is_model_present(
                model_path=model_path
            ):
                logging.info(
                    "Existing production model found in S3."
                )
                return proj1_estimator

            logging.info(
                "No existing production model found in S3."
            )

            return None

        except Exception as e:
            raise MyException(e, sys) from e

    def evaluate_model(self) -> EvaluateModelResponse:
        """
        Method Name : evaluate_model

        Description :
            Evaluates the newly trained model against the existing
            production model stored in S3.

        Output :
            Returns EvaluateModelResponse.
        """

        try:
            # ---------------------------------------------------------
            # 1. Load test data
            # ---------------------------------------------------------
            test_df = pd.read_csv(
                self.data_ingestion_artifact.test_file_path
            )

            x = test_df.drop(
                TARGET_COLUMN,
                axis=1
            )

            y = test_df[TARGET_COLUMN]

            logging.info(
                "Test data loaded and now transforming it for prediction..."
            )

            # ---------------------------------------------------------
            # 2. Load newly trained model
            # ---------------------------------------------------------
            trained_model = load_object(
                file_path=self.model_trainer_artifact.trained_model_file_path
            )

            logging.info(
                "Trained model loaded/exists."
            )

            # F1 score of newly trained model
            trained_model_f1_score = (
                self.model_trainer_artifact
                .metric_artifact
                .f1_score
            )

            logging.info(
                f"F1_Score for this model: {trained_model_f1_score}"
            )

            # ---------------------------------------------------------
            # 3. Get production model from S3
            # ---------------------------------------------------------
            best_model_f1_score = None

            best_model = self.get_best_model()

            # ---------------------------------------------------------
            # 4. Compare models
            # ---------------------------------------------------------
            if best_model is not None:

                logging.info(
                    "Computing F1_Score for production model."
                )

                # Make predictions using production model
                y_hat_best_model = best_model.predict(x)

                # Calculate production model F1
                best_model_f1_score = f1_score(
                    y,
                    y_hat_best_model
                )

                logging.info(
                    f"F1_Score-Production Model: "
                    f"{best_model_f1_score}, "
                    f"F1_Score-New Trained Model: "
                    f"{trained_model_f1_score}"
                )

            else:

                logging.info(
                    "No production model found. "
                    "The newly trained model will be accepted."
                )

            # ---------------------------------------------------------
            # 5. Calculate difference
            # ---------------------------------------------------------
            tmp_best_model_score = (
                0
                if best_model_f1_score is None
                else best_model_f1_score
            )

            difference = (
                trained_model_f1_score
                - tmp_best_model_score
            )

            # ---------------------------------------------------------
            # 6. Decide whether to accept new model
            # ---------------------------------------------------------
            is_model_accepted = (
                best_model_f1_score is None
                or difference
                > self.model_eval_config.changed_threshold_score
            )

            # ---------------------------------------------------------
            # 7. Create evaluation response
            # ---------------------------------------------------------
            result = EvaluateModelResponse(
                trained_model_f1_score=trained_model_f1_score,
                best_model_f1_score=best_model_f1_score,
                is_model_accepted=is_model_accepted,
                difference=difference
            )

            logging.info(
                f"Result: {result}"
            )

            return result

        except Exception as e:
            raise MyException(e, sys) from e

    def initiate_model_evaluation(self) -> ModelEvaluationArtifact:
        """
        Method Name : initiate_model_evaluation

        Description :
            Initiates the complete model evaluation process.

        Output :
            Returns ModelEvaluationArtifact.
        """

        try:

            print(
                "------------------------------------------------------------------------------------------------"
            )

            logging.info(
                "Initialized Model Evaluation Component."
            )

            # Run model evaluation
            evaluate_model_response = (
                self.evaluate_model()
            )

            # S3 model path
            s3_model_path = (
                self.model_eval_config.s3_model_key_path
            )

            # Create evaluation artifact
            model_evaluation_artifact = ModelEvaluationArtifact(
                is_model_accepted=(
                    evaluate_model_response.is_model_accepted
                ),

                s3_model_path=s3_model_path,

                trained_model_path=(
                    self.model_trainer_artifact
                    .trained_model_file_path
                ),

                changed_accuracy=(
                    evaluate_model_response.difference
                )
            )

            logging.info(
                f"Model evaluation artifact: "
                f"{model_evaluation_artifact}"
            )

            return model_evaluation_artifact

        except Exception as e:
            raise MyException(e, sys) from e

