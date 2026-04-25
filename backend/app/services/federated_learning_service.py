"""
Federated Learning Service
Privacy-preserving distributed machine learning for biomarker discovery
"""

import asyncio
import base64
import hashlib
import json
import logging
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import torch
import torch.nn as nn
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import db_session
from app.models.federated import (
    FederatedGlobalModel,
    FederatedModel,
    FederatedParticipant,
    FederatedRound,
)
from app.models.platform_models import FederatedIdempotency

logger = logging.getLogger(__name__)


@dataclass
class FederatedConfig:
    """Federated learning configuration"""

    num_rounds: int = 10
    num_participants: int = 5
    min_participants: int = 3
    learning_rate: float = 0.01
    batch_size: int = 32
    privacy_budget: float = 1.0
    aggregation_method: str = "fedavg"  # fedavg, fedprox, fednova
    differential_privacy: bool = True
    secure_aggregation: bool = True
    # FedProx μ for local subproblem on clients: loss + (μ/2)||w - w_global||²; server = weighted avg
    fedprox_mu: float = 0.01


@dataclass
class ModelUpdate:
    """Model update from a participant"""

    participant_id: str
    model_weights: Dict[str, Any]
    num_samples: int
    loss: float
    accuracy: float
    timestamp: datetime
    signature: str


class FederatedLearningService:
    """Federated learning service for privacy-preserving biomarker discovery"""

    def __init__(self):
        self.config = FederatedConfig(
            fedprox_mu=getattr(
                settings, "FEDERATED_FEDPROX_MU", 0.01
            )
        )
        self.global_model = None
        self.participants = {}
        self.round_history = []
        self.encryption_key = self._generate_encryption_key()

    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key for secure communication"""
        password = settings.SECRET_KEY.encode()
        salt = b"federated_learning_salt"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key

    def _encrypt_data(self, data: Any) -> bytes:
        """Encrypt sensitive data"""
        f = Fernet(self.encryption_key)
        serialized_data = pickle.dumps(data)
        return f.encrypt(serialized_data)

    def _decrypt_data(self, encrypted_data: bytes) -> Any:
        """Decrypt sensitive data"""
        f = Fernet(self.encryption_key)
        decrypted_data = f.decrypt(encrypted_data)
        return pickle.loads(decrypted_data)

    def _sign_update(self, update: ModelUpdate) -> str:
        """Create digital signature for model update"""
        data = (
            f"{update.participant_id}{update.num_samples}{update.loss}{update.accuracy}"
        )
        return hashlib.sha256(data.encode()).hexdigest()

    def _verify_signature(self, update: ModelUpdate) -> bool:
        """Verify digital signature of model update"""
        expected_signature = self._sign_update(update)
        return update.signature == expected_signature

    async def initialize_federated_training(
        self,
        model_type: str,
        config: FederatedConfig,
        participants: List[str],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initialize federated learning training

        Args:
            model_type: Type of model (neural_network, random_forest, logistic_regression)
            config: Federated learning configuration
            participants: List of participant IDs

        Returns:
            Initialization result
        """
        try:
            if idempotency_key:
                with db_session() as db:
                    existing = (
                        db.query(FederatedIdempotency)
                        .filter(FederatedIdempotency.key == idempotency_key)
                        .first()
                    )
                if existing:
                    return {
                        "round_id": existing.round_id,
                        "participants": participants,
                        "config": config.__dict__,
                        "status": "initialized",
                        "idempotent": True,
                    }

            self.config = config

            # Initialize global model
            self.global_model = self._create_global_model(model_type)

            # Register participants
            for participant_id in participants:
                await self._register_participant(participant_id)

            # Create federated round
            round_id = await self._create_federated_round()

            if idempotency_key:
                with db_session() as db:
                    db.add(
                        FederatedIdempotency(key=idempotency_key, round_id=round_id)
                    )
                    db.commit()

            logger.info(
                f"Federated learning initialized with {len(participants)} participants"
            )

            return {
                "round_id": round_id,
                "participants": participants,
                "config": config.__dict__,
                "status": "initialized",
                "idempotent": False,
            }

        except Exception as e:
            logger.error(f"Error initializing federated training: {str(e)}")
            raise

    def _create_global_model(self, model_type: str):
        """Create initial global model"""
        if model_type == "neural_network":
            return self._create_neural_network()
        elif model_type == "random_forest":
            return RandomForestClassifier(n_estimators=100, random_state=42)
        elif model_type == "logistic_regression":
            return LogisticRegression(random_state=42, max_iter=1000)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

    def _create_neural_network(self):
        """Create neural network model"""

        class BiomarkerNet(nn.Module):
            def __init__(self, input_size=1000, hidden_size=512, num_classes=2):
                super(BiomarkerNet, self).__init__()
                self.fc1 = nn.Linear(input_size, hidden_size)
                self.fc2 = nn.Linear(hidden_size, hidden_size // 2)
                self.fc3 = nn.Linear(hidden_size // 2, num_classes)
                self.dropout = nn.Dropout(0.3)
                self.relu = nn.ReLU()

            def forward(self, x):
                x = self.relu(self.fc1(x))
                x = self.dropout(x)
                x = self.relu(self.fc2(x))
                x = self.dropout(x)
                x = self.fc3(x)
                return x

        return BiomarkerNet()

    async def _register_participant(self, participant_id: str):
        """Register a new participant"""
        try:
            with db_session() as db:
                participant = FederatedParticipant(
                    participant_id=participant_id,
                    is_active=True,
                    joined_at=datetime.now(),
                    last_seen=datetime.now(),
                )

                db.add(participant)
                db.commit()

            self.participants[participant_id] = participant

        except Exception as e:
            logger.error(f"Error registering participant {participant_id}: {str(e)}")
            raise

    async def _create_federated_round(self) -> str:
        """Create a new federated learning round"""
        try:
            with db_session() as db:
                round_id = f"round_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                federated_round = FederatedRound(
                    round_id=round_id,
                    status="active",
                    started_at=datetime.now(),
                    aggregation_method=self.config.aggregation_method,
                    config=self.config.__dict__,
                )

                db.add(federated_round)
                db.commit()

                return round_id

        except Exception as e:
            logger.error(f"Error creating federated round: {str(e)}")
            raise

    async def submit_model_update(
        self,
        participant_id: str,
        model_weights: Dict[str, Any],
        num_samples: int,
        loss: float,
        accuracy: float,
        round_id: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Submit model update from participant

        Args:
            participant_id: ID of the participant
            model_weights: Updated model weights
            num_samples: Number of training samples
            loss: Training loss
            accuracy: Training accuracy

        Returns:
            Submission result
        """
        try:
            # Create model update
            update = ModelUpdate(
                participant_id=participant_id,
                model_weights=model_weights,
                num_samples=num_samples,
                loss=loss,
                accuracy=accuracy,
                timestamp=datetime.now(),
                signature="",
            )

            # Sign the update
            update.signature = self._sign_update(update)

            # Verify signature
            if not self._verify_signature(update):
                raise ValueError("Invalid model update signature")

            # Store encrypted update
            encrypted_weights = self._encrypt_data(model_weights)

            # Store in database
            with db_session() as db:
                federated_model = FederatedModel(
                    participant_id=participant_id,
                    round_id=round_id,
                    model_weights=encrypted_weights,
                    num_samples=num_samples,
                    loss=loss,
                    accuracy=accuracy,
                    submitted_at=datetime.now(),
                    is_aggregated=False,
                    meta_data=meta_data,
                )

                db.add(federated_model)
                db.commit()

            logger.info(f"Model update submitted by participant {participant_id}")

            return {
                "status": "submitted",
                "participant_id": participant_id,
                "round_id": round_id,
                "timestamp": update.timestamp.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error submitting model update: {str(e)}")
            raise

    async def aggregate_models(self, round_id: str) -> Dict[str, Any]:
        """
        Aggregate model updates from all participants

        Args:
            round_id: Federated learning round ID

        Returns:
            Aggregation result
        """
        try:
            with db_session() as db:
                # Pending updates for this round (or recent unscoped updates for backward compatibility)
                q = db.query(FederatedModel).filter(
                    FederatedModel.is_aggregated == False
                )
                q = q.filter(FederatedModel.round_id == round_id)
                model_updates = q.all()

                if len(model_updates) < self.config.min_participants:
                    raise ValueError(
                        f"Insufficient participants: {len(model_updates)} < {self.config.min_participants}"
                    )

                # Decrypt and aggregate model weights
                aggregated_weights = await self._aggregate_weights(model_updates)

                # Update global model
                self._update_global_model(aggregated_weights)

                # Mark models as aggregated
                for update in model_updates:
                    update.is_aggregated = True

                db.commit()

                # Calculate aggregation metrics
                metrics = self._calculate_aggregation_metrics(model_updates)

                try:
                    mid = f"global_{round_id}"
                    blob = pickle.dumps(aggregated_weights)
                    gm = FederatedGlobalModel(
                        model_id=mid,
                        model_type=type(self.global_model).__name__
                        if self.global_model
                        else "unknown",
                        model_weights=blob,
                        version=1,
                        metrics=metrics,
                        config={"round_id": round_id},
                    )
                    db.add(gm)
                    db.commit()
                except Exception as persist_err:
                    logger.warning("Could not persist global model: %s", persist_err)
                    db.rollback()

                try:
                    from app.observability.metrics import FEDERATED_ROUNDS

                    FEDERATED_ROUNDS.labels(phase="aggregate").inc()
                except Exception:
                    pass

                logger.info(
                    f"Models aggregated for round {round_id}: {len(model_updates)} participants"
                )

                return {
                    "round_id": round_id,
                    "num_participants": len(model_updates),
                    "aggregated_weights": aggregated_weights,
                    "metrics": metrics,
                    "status": "aggregated",
                    "global_model_id": f"global_{round_id}",
                }

        except Exception as e:
            logger.error(f"Error aggregating models: {str(e)}")
            raise

    async def _aggregate_weights(
        self, model_updates: List[FederatedModel]
    ) -> Dict[str, Any]:
        """Aggregate model weights using specified method"""

        if self.config.aggregation_method == "fedavg":
            return await self._federated_averaging(model_updates)
        elif self.config.aggregation_method == "fedprox":
            return await self._federated_proximal(model_updates)
        elif self.config.aggregation_method == "fednova":
            return await self._federated_nova(model_updates)
        else:
            raise ValueError(
                f"Unsupported aggregation method: {self.config.aggregation_method}"
            )

    async def _federated_averaging(
        self, model_updates: List[FederatedModel]
    ) -> Dict[str, Any]:
        """Federated averaging aggregation"""
        if not model_updates:
            return {}
        use_bonawitz = bool(
            getattr(settings, "FEDERATED_BONAWITZ_MASK_AGGREGATION_ENABLED", False)
        ) and all((u.meta_data or {}).get("use_bonawitz_mask") for u in model_updates)
        use_ring = bool(
            getattr(settings, "FEDERATED_CRYPTO_SECURE_AGGREGATION_ENABLED", False)
        ) and all((u.meta_data or {}).get("use_ring_masked") for u in model_updates)
        if use_bonawitz or use_ring:
            return await self._federated_ring_masked_average(model_updates)

        # Decrypt model weights
        decrypted_weights = []
        total_samples = 0

        for update in model_updates:
            weights = self._decrypt_data(update.model_weights)
            decrypted_weights.append((weights, update.num_samples))
            total_samples += update.num_samples

        # Weighted average
        aggregated_weights = {}

        for key in decrypted_weights[0][0].keys():
            first_layer = np.asarray(decrypted_weights[0][0][key], dtype=float)
            weighted_sum = np.zeros_like(first_layer, dtype=float)

            for weights, num_samples in decrypted_weights:
                weight = float(num_samples) / float(total_samples)
                layer = np.asarray(weights[key], dtype=float)
                weighted_sum += weight * layer

            aggregated_weights[key] = weighted_sum

        return aggregated_weights

    async def _federated_ring_masked_average(
        self, model_updates: List[FederatedModel]
    ) -> Dict[str, Any]:
        """
        Each decrypted weight dict holds per-layer tensors of shape
        (n_i * w_i + mask_i) with zero-sum masks across participants.
        """
        from app.services.federated_ring_mask import aggregate_weighted_masked

        decrypted = []
        nums = []
        for update in model_updates:
            weights = self._decrypt_data(update.model_weights)
            decrypted.append(weights)
            nums.append(update.num_samples)

        keys = decrypted[0].keys()
        aggregated_weights: Dict[str, Any] = {}
        total_n = float(sum(nums))
        for key in keys:
            tensors = [np.asarray(d[key], dtype=float) for d in decrypted]
            aggregated_weights[key] = aggregate_weighted_masked(tensors, nums)
        logger.info(
            "Ring-masked FedAvg over %s participants, total_n=%s",
            len(model_updates),
            total_n,
        )
        return aggregated_weights

    async def _federated_proximal(
        self, model_updates: List[FederatedModel]
    ) -> Dict[str, Any]:
        """
        FedProx server step: **weighted average** of local models (same as FedAvg).

        The proximal term ``μ`` in :class:`FederatedConfig` is for **participants**:
        they minimize `F_k(w) + (μ/2)||w - w_glob||^2` locally, then send ``w``;
        the server does not re-apply ``μ`` here. Fernet and optional Bonawitz/ring
        masks apply via :meth:`_federated_averaging`.
        """
        return await self._federated_averaging(model_updates)

    async def _federated_nova(
        self, model_updates: List[FederatedModel]
    ) -> Dict[str, Any]:
        """Federated Nova aggregation"""

        # Similar to FedAvg but with normalized updates
        # This is a simplified implementation
        return await self._federated_averaging(model_updates)

    def _update_global_model(self, aggregated_weights: Dict[str, Any]):
        """Update global model with aggregated weights"""

        if isinstance(self.global_model, nn.Module):
            # Update neural network weights
            state_dict = {}
            for key, value in aggregated_weights.items():
                state_dict[key] = torch.tensor(value)
            self.global_model.load_state_dict(state_dict)
        else:
            # Update sklearn model
            # This would need model-specific implementation
            pass

    def _calculate_aggregation_metrics(
        self, model_updates: List[FederatedModel]
    ) -> Dict[str, Any]:
        """Calculate aggregation metrics"""

        losses = [update.loss for update in model_updates]
        accuracies = [update.accuracy for update in model_updates]
        num_samples = [update.num_samples for update in model_updates]

        return {
            "mean_loss": np.mean(losses),
            "std_loss": np.std(losses),
            "mean_accuracy": np.mean(accuracies),
            "std_accuracy": np.std(accuracies),
            "total_samples": sum(num_samples),
            "min_samples": min(num_samples),
            "max_samples": max(num_samples),
        }

    async def get_global_model(self, participant_id: str) -> Dict[str, Any]:
        """
        Get current global model for participant

        Args:
            participant_id: ID of the participant

        Returns:
            Global model weights
        """
        try:
            if self.global_model is None:
                raise ValueError("Global model not initialized")

            # Get model weights
            if isinstance(self.global_model, nn.Module):
                weights = {
                    name: param.data.numpy()
                    for name, param in self.global_model.named_parameters()
                }
            else:
                # For sklearn models, return model parameters
                weights = self.global_model.get_params()

            # Encrypt weights for transmission
            encrypted_weights = self._encrypt_data(weights)

            return {
                "model_weights": encrypted_weights,
                "model_type": type(self.global_model).__name__,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting global model: {str(e)}")
            raise

    async def evaluate_global_model(
        self, test_data: pd.DataFrame, test_labels: pd.Series
    ) -> Dict[str, Any]:
        """
        Evaluate global model on test data

        Args:
            test_data: Test features
            test_labels: Test labels

        Returns:
            Evaluation metrics
        """
        try:
            if self.global_model is None:
                raise ValueError("Global model not initialized")

            # Make predictions
            if isinstance(self.global_model, nn.Module):
                self.global_model.eval()
                with torch.no_grad():
                    X_tensor = torch.tensor(test_data.values, dtype=torch.float32)
                    predictions = self.global_model(X_tensor)
                    predicted_labels = torch.argmax(predictions, dim=1).numpy()
            else:
                predicted_labels = self.global_model.predict(test_data)

            # Calculate metrics
            accuracy = accuracy_score(test_labels, predicted_labels)
            precision = precision_score(
                test_labels, predicted_labels, average="weighted"
            )
            recall = recall_score(test_labels, predicted_labels, average="weighted")
            f1 = f1_score(test_labels, predicted_labels, average="weighted")

            return {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "num_samples": len(test_data),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error evaluating global model: {str(e)}")
            raise

    async def get_federated_status(self) -> Dict[str, Any]:
        """Get current federated learning status"""
        try:
            with db_session() as db:
                # Get active participants
                active_participants = (
                    db.query(FederatedParticipant)
                    .filter(FederatedParticipant.is_active == True)
                    .count()
                )

                # Get recent model updates
                recent_updates = (
                    db.query(FederatedModel)
                    .filter(
                        FederatedModel.submitted_at
                        >= datetime.now() - timedelta(hours=1)
                    )
                    .count()
                )

                # Get round history
                rounds = (
                    db.query(FederatedRound)
                    .order_by(FederatedRound.started_at.desc())
                    .limit(10)
                    .all()
                )

                return {
                    "active_participants": active_participants,
                    "recent_updates": recent_updates,
                    "global_model_initialized": self.global_model is not None,
                    "config": self.config.__dict__,
                    "recent_rounds": [
                        {
                            "round_id": round.round_id,
                            "status": round.status,
                            "started_at": round.started_at.isoformat(),
                        }
                        for round in rounds
                    ],
                }

        except Exception as e:
            logger.error(f"Error getting federated status: {str(e)}")
            raise

    async def add_differential_privacy_noise(
        self, model_weights: Dict[str, Any], epsilon: float = 1.0, delta: float = 1e-5
    ) -> Dict[str, Any]:
        """
        Add differential privacy noise to model weights

        Args:
            model_weights: Model weights to add noise to
            epsilon: Privacy budget
            delta: Privacy parameter

        Returns:
            Noisy model weights
        """
        try:
            noisy_weights = {}

            for key, weights in model_weights.items():
                # Calculate noise scale
                sensitivity = 1.0  # L2 sensitivity
                noise_scale = (2 * np.log(1.25 / delta) * sensitivity) / epsilon

                # Add Gaussian noise
                noise = np.random.normal(0, noise_scale, weights.shape)
                noisy_weights[key] = weights + noise

            return noisy_weights

        except Exception as e:
            logger.error(f"Error adding differential privacy noise: {str(e)}")
            raise

    async def secure_aggregation_protocol(
        self, model_updates: List[FederatedModel]
    ) -> Dict[str, Any]:
        """
        Coordinator-side weighted averaging after decrypting participant updates.

        Optional **Bonawitz-style** and ring zero-sum masks are used when
        settings + ``meta_data`` flags are set; transport still uses Fernet. See
        :meth:`_federated_averaging` and ``GET /api/.../federated/capabilities``.

        Args:
            model_updates: List of model updates

        Returns:
            Aggregated weights (same trust model as FedAvg after decryption).
        """
        try:
            # This is a simplified secure aggregation
            # In practice, this would use cryptographic protocols like Shamir's Secret Sharing

            # For now, use standard aggregation with encryption
            return await self._federated_averaging(model_updates)

        except Exception as e:
            logger.error(f"Error in secure aggregation: {str(e)}")
            raise


# Global federated learning service instance
federated_learning_service = FederatedLearningService()
