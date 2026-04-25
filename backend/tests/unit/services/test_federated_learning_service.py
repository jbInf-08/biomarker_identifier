"""
Comprehensive unit tests for federated learning service.
"""
from datetime import datetime

import pytest

from app.services.federated_learning_service import (
    FederatedConfig,
    FederatedLearningService,
    ModelUpdate,
)
from tests.helpers import patch_module_db_session


class TestFederatedLearningService:
    """Test cases for FederatedLearningService."""

    def test_service_initialization(self):
        """Test service initialization."""
        service = FederatedLearningService()
        assert service is not None
        assert service.config is not None
        assert isinstance(service.config, FederatedConfig)

    @pytest.mark.asyncio
    async def test_register_participant(self, db_session):
        """Test registering a participant."""
        from unittest.mock import patch

        service = FederatedLearningService()

        with patch_module_db_session(
            "app.services.federated_learning_service", db_session
        ):
            participant_id = "test_participant_1"
            await service._register_participant(participant_id)

            assert participant_id in service.participants

    @pytest.mark.asyncio
    async def test_start_federated_round(self, db_session):
        """Test starting a federated learning round."""
        from unittest.mock import patch

        service = FederatedLearningService()

        with patch_module_db_session(
            "app.services.federated_learning_service", db_session
        ):
            # Register participants first
            await service._register_participant("p1")
            await service._register_participant("p2")

            round_id = await service._create_federated_round()
            assert round_id is not None
            assert isinstance(round_id, str)

    @pytest.mark.asyncio
    async def test_aggregate_model_updates(self, db_session):
        """Test aggregating model updates."""
        from unittest.mock import patch

        service = FederatedLearningService()
        service.config.min_participants = 2

        with patch_module_db_session(
            "app.services.federated_learning_service", db_session
        ):
            round_id = await service._create_federated_round()

            await service.submit_model_update(
                participant_id="p1",
                model_weights={"layer1": [1.0, 2.0]},
                num_samples=100,
                loss=0.5,
                accuracy=0.8,
                round_id=round_id,
            )

            await service.submit_model_update(
                participant_id="p2",
                model_weights={"layer1": [1.5, 2.5]},
                num_samples=200,
                loss=0.4,
                accuracy=0.85,
                round_id=round_id,
            )

            result = await service.aggregate_models(round_id)

            assert result is not None
            assert "aggregated_weights" in result or "status" in result

    def test_encrypt_decrypt_data(self):
        """Test encryption and decryption."""
        service = FederatedLearningService()

        original_data = {"test": "data", "value": 123}
        encrypted = service._encrypt_data(original_data)
        assert isinstance(encrypted, bytes)

        decrypted = service._decrypt_data(encrypted)
        assert decrypted == original_data

    def test_sign_verify_update(self):
        """Test signing and verifying model updates."""
        service = FederatedLearningService()

        update = ModelUpdate(
            participant_id="p1",
            model_weights={"layer1": [1.0, 2.0]},
            num_samples=100,
            loss=0.5,
            accuracy=0.8,
            timestamp=datetime.now(),
            signature="",
        )

        signature = service._sign_update(update)
        update.signature = signature

        assert service._verify_signature(update) is True
