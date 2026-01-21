"""
Matching Engine Implementations
"""
import threading
from typing import Tuple, Optional
from enum import Enum

from core.interfaces import MatchingEngine
from core.models import MatchResult


class EngineType(Enum):
    DEVICE = "device"
    ONNX = "onnx"


class DeviceMatchingEngine(MatchingEngine):
    """Hardware-based matching using device firmware"""

    def __init__(self, sensor):
        """
        Args:
            sensor: FingerprintReader instance
        """
        self._sensor = sensor
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "Device Hardware"

    def is_available(self) -> bool:
        """Check if device is connected and ready"""
        return self._sensor is not None and self._sensor.dev is not None

    def enroll(self, image: bytes, user_id: int) -> Tuple[bool, str]:
        """Enroll fingerprint using device"""
        with self._lock:
            try:
                success, assigned_id = self._sensor.add_user(user_id)
                if success:
                    return True, ""
                else:
                    return False, "Device enrollment failed"
            except Exception as e:
                return False, str(e)

    def match(self, image: bytes, timeout_sec: float = 10.0) -> MatchResult:
        """Match fingerprint using device hardware"""
        with self._lock:
            try:
                matched, user_id = self._sensor.match_fingerprint(timeout_sec)
                return MatchResult(
                    matched=matched,
                    user_id=user_id if matched else 0,
                    confidence=1.0 if matched else 0.0,
                    engine_name=self.name
                )
            except Exception as e:
                return MatchResult(
                    matched=False,
                    engine_name=self.name
                )

    def verify(self, image: bytes, user_id: int) -> Tuple[bool, float]:
        """Device doesn't support 1:1 verification directly"""
        # Use 1:N match and check if matched user_id equals target
        result = self.match(image)
        if result.matched and result.user_id == user_id:
            return True, 1.0
        return False, 0.0

    def delete(self, user_id: int) -> bool:
        """Delete enrollment from device"""
        with self._lock:
            try:
                return self._sensor.delete_user(user_id)
            except Exception:
                return False

    def delete_all(self) -> bool:
        """Delete all enrollments from device"""
        with self._lock:
            try:
                return self._sensor.delete_all()
            except Exception:
                return False

    def get_enrolled_count(self) -> int:
        """Get enrolled count from device"""
        with self._lock:
            try:
                return self._sensor.get_user_count()
            except Exception:
                return -1


class ONNXMatchingEngine(MatchingEngine):
    """AI-based matching using ONNX Runtime (placeholder for future)"""

    def __init__(self, model_path: Optional[str] = None):
        self._model_path = model_path
        self._model = None
        self._embeddings = {}  # user_id -> embedding vector

    @property
    def name(self) -> str:
        return "ONNX Runtime"

    def is_available(self) -> bool:
        """Check if ONNX model is loaded"""
        return self._model is not None

    def load_model(self, model_path: str) -> bool:
        """Load ONNX model"""
        try:
            import onnxruntime as ort
            self._model = ort.InferenceSession(model_path)
            self._model_path = model_path
            return True
        except Exception:
            return False

    def enroll(self, image: bytes, user_id: int) -> Tuple[bool, str]:
        """Extract embedding and store"""
        if not self.is_available():
            return False, "ONNX model not loaded"

        try:
            embedding = self._extract_embedding(image)
            if embedding is not None:
                self._embeddings[user_id] = embedding
                return True, ""
            return False, "Failed to extract embedding"
        except Exception as e:
            return False, str(e)

    def match(self, image: bytes, timeout_sec: float = 10.0) -> MatchResult:
        """Match against all enrolled embeddings"""
        if not self.is_available():
            return MatchResult(matched=False, engine_name=self.name)

        try:
            query_embedding = self._extract_embedding(image)
            if query_embedding is None:
                return MatchResult(matched=False, engine_name=self.name)

            best_match_id = 0
            best_confidence = 0.0

            for user_id, stored_embedding in self._embeddings.items():
                confidence = self._compare_embeddings(query_embedding, stored_embedding)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match_id = user_id

            # Threshold for match (configurable)
            threshold = 0.7
            matched = best_confidence >= threshold

            return MatchResult(
                matched=matched,
                user_id=best_match_id if matched else 0,
                confidence=best_confidence,
                engine_name=self.name
            )
        except Exception:
            return MatchResult(matched=False, engine_name=self.name)

    def verify(self, image: bytes, user_id: int) -> Tuple[bool, float]:
        """Verify against specific user"""
        if user_id not in self._embeddings:
            return False, 0.0

        try:
            query_embedding = self._extract_embedding(image)
            if query_embedding is None:
                return False, 0.0

            confidence = self._compare_embeddings(
                query_embedding,
                self._embeddings[user_id]
            )

            threshold = 0.7
            return confidence >= threshold, confidence
        except Exception:
            return False, 0.0

    def delete(self, user_id: int) -> bool:
        """Delete stored embedding"""
        if user_id in self._embeddings:
            del self._embeddings[user_id]
            return True
        return False

    def delete_all(self) -> bool:
        """Delete all embeddings"""
        self._embeddings.clear()
        return True

    def get_enrolled_count(self) -> int:
        """Get enrolled count"""
        return len(self._embeddings)

    def _extract_embedding(self, image: bytes) -> Optional[list]:
        """Extract embedding vector from image using ONNX model"""
        if self._model is None:
            return None

        try:
            import numpy as np

            # Preprocess image
            img_array = np.frombuffer(image, dtype=np.uint8)
            img_array = img_array.reshape((1, 1, 192, 192)).astype(np.float32)
            img_array = img_array / 255.0

            # Run inference
            input_name = self._model.get_inputs()[0].name
            output = self._model.run(None, {input_name: img_array})

            return output[0][0].tolist()
        except Exception:
            return None

    def _compare_embeddings(self, emb1: list, emb2: list) -> float:
        """Compare two embeddings using cosine similarity"""
        try:
            import numpy as np
            a = np.array(emb1)
            b = np.array(emb2)
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        except Exception:
            return 0.0


class MatchingEngineFactory:
    """Factory for creating matching engines"""

    @staticmethod
    def create(engine_type: EngineType, **kwargs) -> MatchingEngine:
        """Create matching engine by type"""
        if engine_type == EngineType.DEVICE:
            sensor = kwargs.get('sensor')
            if sensor is None:
                raise ValueError("sensor required for device engine")
            return DeviceMatchingEngine(sensor)

        elif engine_type == EngineType.ONNX:
            model_path = kwargs.get('model_path')
            engine = ONNXMatchingEngine(model_path)
            if model_path:
                engine.load_model(model_path)
            return engine

        else:
            raise ValueError(f"Unknown engine type: {engine_type}")
