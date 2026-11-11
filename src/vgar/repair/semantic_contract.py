"""Host-pinned input/output examples executed by the existing pytest runner."""
import sys

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class ContractExample(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str = Field(pattern=r"^[A-Za-z0-9_]+$", min_length=1, max_length=80)
    module: str = Field(pattern=r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$")
    function: str = Field(pattern=r"^[A-Za-z_]\w*$")
    args: tuple[JsonValue, ...] = ()
    kwargs: dict[str, JsonValue] = Field(default_factory=dict)
    expected: JsonValue

    @property
    def node_id(self) -> str:
        return "vgar_contract::" + self.case_id


class SemanticContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    examples: tuple[ContractExample, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [example.case_id for example in self.examples]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate semantic contract case ID")
        return self


class ContractExecutor:
    def __init__(self, executor, payload):
        self.executor, self.payload = executor, payload

    def run(self, argv, cwd, timeout_seconds):
        if argv[:3] == (sys.executable, "-m", "pytest"):
            argv = (*argv, "-p", "vgar.repair.semantic_contract_plugin", "--vgar-contract=" + self.payload)
        return self.executor.run(argv, cwd, timeout_seconds)
