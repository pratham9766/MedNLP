"""Optional Transformers adapter; failures stay visible and return no predictions."""
import os
import time

DEFAULT_MODEL = "d4data/biomedical-ner-all"
DEFAULT_REVISION = "e2272cd5d96cb445524015fc5d9c1e198224a3bc"
MODEL_LABEL_MAP = {
    "Lab_value": "laboratory_result", "Disease_disorder": "diagnosis_or_symptom",
    "Sign_symptom": "diagnosis_or_symptom", "Medication": "medication",
    "Diagnostic_procedure": "diagnostic_procedure",
}

class BiomedicalNerAdapter:
    def __init__(self, model_id=None, loader=None):
        self.model_id = model_id or os.getenv("MEDNLP_NER_MODEL", DEFAULT_MODEL)
        self.revision = os.getenv("MEDNLP_NER_REVISION", DEFAULT_REVISION)
        self.loader = loader or self._load_pipeline
        self.pipeline = None
        self.error = None
        self.load_seconds = None

    @staticmethod
    def _load_pipeline(model_id, revision):
        from transformers import pipeline
        return pipeline("token-classification", model=model_id, revision=revision, aggregation_strategy="simple")

    def load(self):
        started=time.perf_counter()
        try:
            self.pipeline = self.loader(self.model_id, self.revision)
            model=getattr(self.pipeline,"model",None); tokenizer=getattr(self.pipeline,"tokenizer",None)
            config=getattr(model,"config",None)
            labels=sorted({str(v).removeprefix("B-").removeprefix("I-") for v in getattr(config,"id2label",{}).values()}) if config else []
            parameter_count=sum(p.numel() for p in model.parameters()) if model is not None else None
            self.load_seconds=time.perf_counter()-started
            return {"status":"available", "model_id":self.model_id, "revision":self.revision,"tokenizer_class":type(tokenizer).__name__ if tokenizer else None,"tokenizer_is_fast":getattr(tokenizer,"is_fast",None),"supported_model_labels":labels,"max_position_embeddings":getattr(config,"max_position_embeddings",None),"parameter_count":parameter_count,"device":str(getattr(self.pipeline,"device","unknown")),"load_seconds":self.load_seconds}
        except Exception as exc:
            self.load_seconds=time.perf_counter()-started
            self.error = f"{type(exc).__name__}: {exc}"
            self.pipeline = None
            return {"status":"unavailable", "model_id":self.model_id, "revision":self.revision,"load_seconds":self.load_seconds, "error":self.error}

    def predict(self, text, page=1):
        if self.pipeline is None:
            state = self.load()
            if state["status"] != "available": return [], state
        predictions=[]
        try:
            for item in self.pipeline(text):
                label=str(item.get("entity_group", item.get("entity", ""))).removeprefix("B-").removeprefix("I-")
                entity_type=MODEL_LABEL_MAP.get(label)
                start,end=item.get("start"),item.get("end")
                if not entity_type or not isinstance(start,int) or not isinstance(end,int) or end<=start: continue
                original=text[start:end]
                predictions.append({"entity_id":f"{self.model_id}:{page}:{start}:{end}","entity_type":entity_type,"source_page":page,"start_char":start,"end_char":end,"original_text":original,"normalized_value":None,"unit":None,"reference_interval":None,"negation":None,"uncertainty":None,"temporality":None,"assertion_status":None})
            return predictions, {"status":"available","model_id":self.model_id,"revision":self.revision}
        except Exception as exc:
            self.error=f"{type(exc).__name__}: {exc}"; self.pipeline=None
            return [], {"status":"failed","model_id":self.model_id,"error":self.error}
