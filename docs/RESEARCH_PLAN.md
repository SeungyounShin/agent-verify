# Self-Verification Strategies in Agent Harness Design: A Systematic Empirical Study

## Working Title
**"Verify, Then Trust: A Systematic Study of Self-Verification Strategies in Agentic Coding Harnesses"**

---

## 1. Motivation & Problem Statement

### 1.1 Core Observation
최근 산업계에서 동일한 LLM 모델을 사용하더라도 **agent harness의 설계**에 따라 벤치마크 성능이 크게 달라진다는 사실이 반복적으로 관찰되고 있다.

- **LangChain (2025.02)**: GPT-5.2-Codex를 고정한 채 harness만 변경하여 Terminal-Bench 2.0에서 52.8% → 66.5% (+13.7pp) 달성. 가장 큰 성능 향상 요인은 **self-verification loop**.
- **Anthropic (2025.11)**: Long-running agent의 주요 failure mode가 "테스트 없이 완료 선언" — self-verification 부재가 핵심 원인.
- **Anthropic (2026.02)**: Infrastructure configuration만으로 agentic coding 벤치마크에서 6pp 차이 발생 — 모델 간 leaderboard gap보다 큰 경우도 있음.
- **Ralph pattern (2025.07~)**: Geoffrey Huntley가 개발한 "naive persistence" 패턴이 viral. 핵심은 LLM의 자기 평가를 신뢰하지 않고, 외부 verification이 통과할 때까지 fresh context로 반복 실행.

### 1.2 Research Gap
이러한 관찰들이 blog post, tweet, GitHub repo 수준에서 공유되고 있으나:
- **체계적 ablation study**가 부재: 어떤 verification 전략이 왜, 얼마나 효과적인지 controlled experiment가 없음
- **설계 차원의 분류(taxonomy)**가 없음: verification method, granularity, failure recovery 등의 축이 정리되지 않음
- **cost-benefit 분석**이 없음: verification overhead(추가 token, 시간)와 성능 향상 간의 trade-off를 정량화한 연구가 없음

### 1.3 Why This Matters Academically
- "Agent harness design"은 현재 산업계에서 가장 활발히 탐구되는 영역이지만, 학술적 체계화가 전무
- SWE-agent (ICLR 2024)가 "Agent-Computer Interface"라는 개념으로 harness 설계의 중요성을 보인 선례가 있으나, verification에 초점을 맞춘 연구는 없음
- Self-verification은 coding agent에 국한되지 않고 모든 agentic system에 적용 가능한 일반적 설계 원칙

---

## 2. Research Question

### Primary RQ
**"Agent harness에서 self-verification 전략의 설계 차원(method, granularity, failure recovery)이 task completion rate과 efficiency에 어떤 영향을 미치는가?"**

### Sub-RQs
- **RQ1**: Verification method(없음 / self-review / test execution / spec comparison / e2e browser)에 따른 task completion 차이는 어떠한가?
- **RQ2**: Verification granularity(task-end-only / per-feature / per-file-change)에 따른 성능-효율 trade-off는 어떠한가?
- **RQ3**: Verification 실패 시 failure recovery 전략(retry-in-context / compaction+retry / fresh-context restart)이 recovery 성공률에 미치는 영향은?
- **RQ4**: 위 세 차원 간에 유의미한 interaction effect가 존재하는가?

---

## 3. Hypotheses

### H1: Verification Method
**외부 도구를 통한 verification(test execution, e2e)이 LLM 자체의 self-review보다 유의미하게 높은 task completion rate를 보인다.**

근거:
- LangChain 관찰: "Agents would write a solution, re-read their own code, decide it looked fine, and stop" — self-review의 구조적 한계
- Ralph 철학: "LLM의 자기 평가가 unreliable하니까 외부 verification을 강제하라"
- Anthropic long-running agent: Puppeteer를 통한 e2e testing이 "code alone으로는 발견할 수 없는 버그"를 잡음

### H2: Verification Granularity
**중간 수준의 granularity(per-feature)가 양 극단(task-end-only, per-file-change)보다 최적의 성능-효율 균형을 보인다.**

근거:
- Too coarse (task-end-only): 누적된 오류가 너무 커서 recovery가 어려움
- Too fine (per-file-change): overhead가 과도하고, 중간 상태에서의 false negative가 많음 (아직 완성 안 된 코드를 검증하려 하므로)
- Ralph 설계: story(feature) 단위로 verify하는 것이 실무적으로 효과적이었음

### H3: Failure Recovery
**Fresh-context restart(Ralph 패턴)가 compaction+retry보다 높은 recovery 성공률을 보이되, 단순한 retry-in-context는 가장 낮은 성공률을 보인다.**

근거:
- Ralph의 핵심 insight: "No compaction, no degradation" — 실패한 context를 정리하는 것보다 깨끗한 상태에서 다시 시작하는 게 낫다
- Anthropic: compaction이 "doesn't always pass perfectly clear instructions to the next agent"
- 단, fresh restart는 이전 시도에서 얻은 정보를 잃을 수 있으므로 trade-off 존재

### H4: Interaction Effects
**Verification method와 failure recovery 간에 interaction effect가 존재한다: test execution + fresh-context 조합이 다른 조합보다 불균형적으로 높은 성능을 보인다.**

근거:
- Test execution은 구체적인 failure signal을 생성하고, fresh context에서 이 signal만 전달하면 이전 실패의 noise 없이 targeted fix가 가능
- Self-review + fresh restart는 이전에 "뭐가 잘못됐는지" 구체적 signal이 없으므로 효과 감소

---

## 4. Experimental Design

### 4.1 Overview

```
Fixed:
- Model: Claude Sonnet 4.6 (primary), GPT-5.2-Codex (replication)
- Base tools: file read/write, bash execution, git operations
- System prompt: minimal baseline (동일)

Independent Variables:
- Verification Method (5 levels)
- Verification Granularity (3 levels)  
- Failure Recovery Strategy (3 levels)

Dependent Variables:
- Task completion rate (primary)
- Token usage (efficiency)
- Wall-clock time
- Number of tool calls
- Recovery success rate (verification 실패 후 최종 성공 비율)

Benchmarks:
- SWE-bench Verified (primary)
- Terminal-Bench 2.0 (secondary)
```

### 4.2 Independent Variable Definitions

#### Verification Method

| Level | Name | Description | Implementation |
|-------|------|-------------|----------------|
| V0 | **None** | Agent가 스스로 완료를 선언하면 즉시 종료 | Baseline — 아무런 verification 없음 |
| V1 | **Self-Review** | Agent에게 자기 결과물을 다시 읽고 평가하라고 prompting | 시스템 프롬프트에 "Review your changes and verify correctness" 추가 |
| V2 | **Test Execution** | Agent가 작성/수정한 코드에 대해 기존 테스트 실행 | `pytest` / `npm test` 결과를 feedback으로 제공 |
| V3 | **Spec Comparison** | 원본 task specification 대비 결과물을 LLM이 비교 검증 | 별도 verification prompt: "Compare your output against the original spec: {spec}" |
| V4 | **E2E Verification** | 외부 도구(browser automation, script)로 end-to-end 검증 | Puppeteer/Playwright로 UI 테스트 또는 integration test script 실행 |

#### Verification Granularity

| Level | Name | Description |
|-------|------|-------------|
| G1 | **Task-End-Only** | 전체 task 완료 시점에만 한 번 verification |
| G2 | **Per-Feature** | 각 feature/story 단위로 verification (Ralph 스타일) |
| G3 | **Per-Step** | 의미 있는 코드 변경(file write/edit) 후마다 verification |

#### Failure Recovery Strategy

| Level | Name | Description |
|-------|------|-------------|
| R1 | **Retry-in-Context** | 동일 context 내에서 실패 feedback을 주고 재시도 |
| R2 | **Compaction + Retry** | Context를 compaction(요약) 후 실패 정보와 함께 재시도 |
| R3 | **Fresh-Context Restart** | 완전히 새로운 context window에서 재시작 (file system + git 상태는 보존, Ralph 스타일) |

### 4.3 Experimental Matrix

전체 조합(5 × 3 × 3 = 45)은 비용상 불가능하므로, 다음 전략으로 축소:

**Phase 1: Method Ablation (RQ1)**
- G2 (per-feature) + R1 (retry-in-context)으로 고정
- V0 ~ V4 비교 → 5 conditions
- SWE-bench Verified 300 instances × 3 trials = 4,500 runs

**Phase 2: Granularity Ablation (RQ2)**
- Phase 1에서 가장 좋은 method(예: V2) + R1 고정
- G1, G2, G3 비교 → 3 conditions  
- SWE-bench Verified 300 instances × 3 trials = 2,700 runs

**Phase 3: Recovery Ablation (RQ3)**
- Phase 1 best method + Phase 2 best granularity 고정
- R1, R2, R3 비교 → 3 conditions
- SWE-bench Verified 300 instances × 3 trials = 2,700 runs

**Phase 4: Interaction Effects (RQ4)**
- Top-2 methods × 3 recovery strategies = 6 conditions
- SWE-bench Verified 300 instances × 2 trials = 3,600 runs

**Phase 5: Cross-Benchmark Validation**
- Phase 1~3의 best configuration을 Terminal-Bench 2.0에서 검증
- 89 tasks × 3 trials per condition

**Total estimated runs**: ~15,000+ (비용 추정 필요)

### 4.4 Infrastructure & Controls

Anthropic의 "Quantifying Infrastructure Noise" (2026.02) 블로그의 권고사항을 반영:

- **Resource configuration 고정**: 모든 실험에서 동일한 container spec (CPU, RAM, timeout)
- **Time-of-day 통제**: API latency 변동을 줄이기 위해 동일 시간대에 실행하거나, 조건 간 랜덤 배치
- **다중 trial**: 각 condition당 최소 3회 반복, 분산 보고
- **Container 격리**: 각 task instance가 독립된 환경에서 실행

### 4.5 Implementation Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Experiment Runner                    │
│  - Benchmark loader (SWE-bench / Terminal-Bench)     │
│  - Condition configurator                            │
│  - Result logger                                     │
└───────────────┬─────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────┐
│              Modular Agent Harness                    │
│  ┌──────────┐ ┌──────────────┐ ┌─────────────────┐ │
│  │ Base      │ │ Verification │ │ Recovery        │ │
│  │ Agent     │ │ Module       │ │ Module          │ │
│  │ (fixed)   │ │ (swappable)  │ │ (swappable)     │ │
│  └──────────┘ └──────────────┘ └─────────────────┘ │
│                                                      │
│  Components:                                         │
│  - System prompt (fixed baseline)                    │
│  - Tool set (fixed: file ops, bash, git)             │
│  - LLM client (Claude API / OpenAI API)              │
│  - Verification interface (pluggable)                │
│  - Recovery interface (pluggable)                    │
└─────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────┐
│              Sandbox Environment                      │
│  - Docker container per task                         │
│  - Fixed resource allocation                         │
│  - Git-initialized workspace                         │
│  - Benchmark-specific setup (repo clone, deps)       │
└─────────────────────────────────────────────────────┘
```

---

## 5. Benchmarks

### 5.1 SWE-bench Verified (Primary)

- **왜**: 가장 널리 인정받는 agentic coding 벤치마크, 충분히 복잡한 multi-step task
- **규모**: Verified subset (500 instances) 중 300개 사용
- **평가**: Pass@1 (resolve rate)
- **장점**: 기존 test suite가 있어서 V2(test execution)의 자연스러운 verification signal 제공
- **Setup**: SWE-bench의 공식 Docker harness 위에 우리의 verification/recovery module을 plug-in

### 5.2 Terminal-Bench 2.0 (Secondary)

- **왜**: LangChain이 harness engineering 실험에 사용, cross-domain(ML, debugging, bio 등) 89 tasks
- **규모**: 전체 89 tasks
- **평가**: Task reward score (0 or 1)
- **장점**: LangChain의 결과와 직접 비교 가능, 각 task에 built-in verification logic 있음
- **Setup**: Harbor framework 활용

### 5.3 Metrics

| Metric | Description | How Measured |
|--------|-------------|--------------|
| **Resolve Rate** | Task 성공 비율 (primary) | SWE-bench: test pass, Terminal-Bench: reward |
| **Token Usage** | 총 input + output tokens | API usage logging |
| **Wall-Clock Time** | Task당 소요 시간 | Timestamp logging |
| **Tool Call Count** | 총 tool invocation 횟수 | Agent trace logging |
| **Verification Overhead** | Verification에 소비된 token/시간 비율 | Verification module 내부 logging |
| **Recovery Success Rate** | Verification 실패 후 최종 성공 비율 | Recovery module tracking |
| **First-Pass Success Rate** | Verification 없이도 성공했을 비율 (counterfactual) | V0 baseline 대비 |

---

## 6. Related Work

### 6.1 Directly Related (Agent Harness Design)

| Paper/Source | Year | Key Contribution | Gap |
|---|---|---|---|
| SWE-agent (Yang et al.) | 2024 | Agent-Computer Interface 개념 제안, interface design이 성능에 영향 | Verification에 초점 없음, 체계적 ablation 아님 |
| Anthropic "Context Engineering" | 2025.09 | Context를 finite resource로 보는 framework, compaction/note-taking/sub-agent | Blog, verification은 간략 언급만 |
| Anthropic "Effective Harnesses" | 2025.11 | Long-running agent failure modes 식별, initializer/coding agent 패턴 | Controlled experiment 아님, 단일 설계만 제시 |
| LangChain "Harness Engineering" | 2026.02 | Harness만으로 +13.7pp, self-verification이 top contributor | System prompt + tools + middleware 동시 변경, 개별 요인 분리 불가 |
| Ralph (Huntley) | 2025.07 | Fresh-context loop + file-based state + external verification | Engineering artifact, 학술적 분석/비교 없음 |
| Anthropic "Infrastructure Noise" | 2026.02 | Infrastructure만으로 6pp 차이, benchmark reliability 문제 제기 | Harness software design이 아닌 hardware/infra 초점 |

### 6.2 Conceptually Related

| Paper | Year | Relevance |
|---|---|---|
| MemGPT (Packer et al.) | 2023 | Virtual context management — compaction/recovery와 관련 |
| DSPy (Khattab et al.) | 2023 | Prompt pipeline 자동 최적화 — harness 최적화의 자동화 관점 |
| Reflexion (Shinn et al.) | 2023 | Self-reflection을 통한 agent 개선 — self-review(V1)와 관련 |
| ToolBench (Qin et al.) | 2023 | Tool use 벤치마크 — tool 차원은 우리가 고정하는 변수 |
| AgentBench (Liu et al.) | 2023 | Multi-environment agent 벤치마크 |
| LangChain "Multi-Agent Bench" | 2025.06 | τ-bench에 distractor 추가하여 architecture 비교 |
| Vercel "Ralph Loop Agent" | 2026 | Ralph 패턴의 SDK 구현, verifyCompletion 인터페이스 정의 |

### 6.3 Positioning
- Reflexion이 가장 가까운 선행 연구이나, 이는 agent의 **internal reflection** prompt에 초점. 우리는 **harness-level verification** (외부 도구, 실행 환경) 포함하여 더 넓은 설계 공간을 다룸.
- SWE-agent가 "interface design matters"를 보였다면, 우리는 "verification design matters"를 보이는 것.

---

## 7. Expected Contributions

1. **Self-verification design space의 첫 번째 체계적 taxonomy**: method, granularity, failure recovery 3개 차원으로 분류
2. **Controlled ablation study**: 동일 모델에서 verification 전략만 변경했을 때의 성능 차이를 정량화
3. **Cost-benefit 분석**: Verification overhead 대비 성능 향상의 trade-off curve 제시
4. **Cross-benchmark 검증**: SWE-bench와 Terminal-Bench에서의 일관성 확인
5. **Practical guidelines**: 어떤 조건에서 어떤 verification 전략이 최적인지에 대한 actionable recommendation

---

## 8. Target Venues

| Venue | Fit | Deadline (estimated) |
|---|---|---|
| **ICLR 2027** | Agent track 확대 중, empirical study 환영 | 2026.09~10 |
| **NeurIPS 2026 Datasets & Benchmarks** | Benchmark 방법론 contribution으로 제출 가능 | 2026.05~06 |
| **COLM 2026** | Language model 실용적 활용에 open | TBD |
| **ICML 2027** | Agent/LLM workshop | 2026.01~02 |
| **ArXiv preprint** | 빠른 공개로 선점 효과 | ASAP |

**추천 전략**: ArXiv preprint 먼저 공개 → ICLR 2027 또는 NeurIPS 2026 D&B track 제출

---

## 9. Implementation Plan

### 9.1 Phase 0: Infrastructure Setup (Week 1-2)

```
Tasks:
- [ ] Modular agent harness framework 구현
  - Base agent loop (tool calling + LLM interaction)
  - Pluggable Verification interface
  - Pluggable Recovery interface
  - Trace/logging system
- [ ] SWE-bench Verified evaluation pipeline 셋업
  - Docker sandbox per task
  - Official SWE-bench harness 연동
  - Result collection & storage
- [ ] Terminal-Bench 2.0 evaluation pipeline 셋업
  - Harbor framework 연동 또는 자체 구현
- [ ] Cost estimation: 1 full run의 API 비용 측정
- [ ] CI/CD: 실험 재현을 위한 config management
```

#### Key Implementation Details

**Modular Harness 구조:**
```python
class AgentHarness:
    def __init__(self, config: HarnessConfig):
        self.llm_client = LLMClient(config.model)
        self.tools = ToolSet(config.tools)
        self.verifier = VerifierFactory.create(config.verification_method)
        self.recovery = RecoveryFactory.create(config.recovery_strategy)
        self.granularity = config.verification_granularity
        self.logger = ExperimentLogger(config.experiment_id)
    
    def run(self, task: Task) -> Result:
        """Main agent loop with pluggable verification & recovery."""
        context = self.initialize_context(task)
        
        while not self.is_complete(context):
            # Agent takes action
            action = self.llm_client.generate(context)
            result = self.tools.execute(action)
            context.append(action, result)
            
            # Verification check (based on granularity)
            if self.should_verify(context, self.granularity):
                verification = self.verifier.verify(context, task)
                self.logger.log_verification(verification)
                
                if not verification.passed:
                    context = self.recovery.recover(
                        context, verification, task
                    )
        
        return self.evaluate(context, task)
```

**Verification Interface:**
```python
class Verifier(ABC):
    @abstractmethod
    def verify(self, context: Context, task: Task) -> VerificationResult:
        pass

class NoVerification(Verifier):
    """V0: No verification, agent self-declares completion."""
    
class SelfReviewVerifier(Verifier):
    """V1: Ask LLM to review its own output."""
    
class TestExecutionVerifier(Verifier):
    """V2: Run existing test suite."""
    
class SpecComparisonVerifier(Verifier):
    """V3: LLM compares output against original spec."""
    
class E2EVerifier(Verifier):
    """V4: External tool-based end-to-end verification."""
```

**Recovery Interface:**
```python
class RecoveryStrategy(ABC):
    @abstractmethod
    def recover(self, context, verification, task) -> Context:
        pass

class RetryInContext(RecoveryStrategy):
    """R1: Append failure feedback, continue in same context."""

class CompactAndRetry(RecoveryStrategy):
    """R2: Summarize context, include failure info, continue."""
    
class FreshRestart(RecoveryStrategy):
    """R3: Start new context window, preserve filesystem state (Ralph-style)."""
```

### 9.2 Phase 1: Method Ablation (Week 3-4)

```
Tasks:
- [ ] V0~V4 각각 구현 및 단위 테스트
- [ ] SWE-bench 300 instances × V0~V4 × 3 trials 실행
- [ ] 결과 수집: resolve rate, token usage, time, tool calls
- [ ] 통계 분석: paired comparison, significance testing
- [ ] 초기 결과 정리 및 가설 수정 여부 판단
```

### 9.3 Phase 2: Granularity Ablation (Week 5-6)

```
Tasks:
- [ ] Phase 1 best method 선택
- [ ] G1, G2, G3 구현
- [ ] SWE-bench 300 instances × G1~G3 × 3 trials 실행
- [ ] Cost-benefit curve 생성: (verification overhead) vs (resolve rate improvement)
- [ ] Sweet spot 분석
```

### 9.4 Phase 3: Recovery Ablation (Week 7-8)

```
Tasks:
- [ ] R1, R2, R3 구현 (특히 R3 fresh-restart는 Ralph 패턴 충실히 재현)
- [ ] SWE-bench 300 instances × R1~R3 × 3 trials 실행
- [ ] Recovery-specific metrics 분석: recovery success rate, recovery token cost
- [ ] Fresh restart의 정보 손실 vs context 오염 제거 trade-off 분석
```

### 9.5 Phase 4: Interaction & Cross-Benchmark (Week 9-10)

```
Tasks:
- [ ] Top-2 methods × 3 recovery strategies factorial 실행
- [ ] Interaction effect 통계 분석 (two-way ANOVA or equivalent)
- [ ] Best configuration을 Terminal-Bench 2.0에서 검증
- [ ] Cross-benchmark consistency 분석
```

### 9.6 Phase 5: Paper Writing (Week 11-14)

```
Tasks:
- [ ] Introduction & motivation
- [ ] Related work section
- [ ] Experimental setup section (reproducibility 강조)
- [ ] Results & analysis
- [ ] Discussion: practical guidelines, limitations, future work
- [ ] Model replication (Sonnet → Codex로 재현)
- [ ] Camera-ready preparation
```

---

## 10. Risk & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| API 비용 초과 | 실험 축소 필요 | Phase 1에서 비용 측정 후 조정, SWE-bench subset 사용 |
| SWE-bench task에서 verification이 trivial | V0과 V2+ 차이가 작음 | 난이도별 stratified 분석, Terminal-Bench로 보완 |
| 모든 verification이 비슷한 결과 | Negative result | Negative result도 가치 있음 (예: "어떤 방법이든 있기만 하면 된다") |
| 실험 중 모델 버전 변경 | 재현성 문제 | 실험 시작 전 모델 버전 고정, API snapshot 기록 |
| 누군가 비슷한 연구 선 공개 | Scoop 위험 | ArXiv preprint 빠르게 공개, 차별화 포인트 강조 |

---

## 11. Key References

### Industry Sources (Primary Motivation)
- Anthropic. "Effective context engineering for AI agents." Engineering Blog, Sep 2025. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Anthropic. "Effective harnesses for long-running agents." Engineering Blog, Nov 2025. https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic. "Quantifying infrastructure noise in agentic coding evals." Engineering Blog, Feb 2026.
- LangChain. "Improving Deep Agents with harness engineering." Blog, Feb 2026. https://blog.langchain.com/improving-deep-agents-with-harness-engineering/
- LangChain. "Deep Agents." Blog, Jul 2025. https://blog.langchain.com/deep-agents/
- LangChain. "Benchmarking Multi-Agent Architectures." Blog, Jun 2025. https://blog.langchain.com/benchmarking-multi-agent-architectures/
- Huntley, G. "Ralph." GitHub, 2025. https://github.com/snarktank/ralph
- Vercel Labs. "Ralph Loop Agent." GitHub, 2026. https://github.com/vercel-labs/ralph-loop-agent

### Academic Papers
- Yang, J. et al. "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering." ICLR 2024.
- Shinn, N. et al. "Reflexion: Language Agents with Verbal Reinforcement Learning." NeurIPS 2023.
- Packer, C. et al. "MemGPT: Towards LLMs as Operating Systems." 2023.
- Khattab, O. et al. "DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines." ICLR 2024.
- Jimenez, C.E. et al. "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?" ICLR 2024.

### Benchmarks
- SWE-bench Verified: https://github.com/princeton-nlp/SWE-bench
- Terminal-Bench 2.0: https://terminal-bench.com (or relevant GitHub)
- Harbor (evaluation framework): https://github.com/harbor-ai/harbor

---

## 12. Notes for Claude Code

### 이 프로젝트를 진행할 때 주의사항

1. **Modular 설계 최우선**: Verification module과 Recovery module은 반드시 pluggable interface로. 실험 조건 추가/변경이 config 변경만으로 가능해야 함.

2. **Logging 철저히**: 모든 LLM call, tool call, verification result, recovery attempt를 structured log (JSON)로 저장. 나중에 분석할 때 필요.

3. **비용 관리**: Phase 1 시작 전에 반드시 소규모 pilot (SWE-bench 10 instances × 1 trial)으로 조건당 비용 추정. 전체 예산 내에서 실험 규모 조정.

4. **재현성**: 모든 실험 config를 YAML/JSON으로 관리. Random seed, 모델 버전, container spec, timestamp 등 기록.

5. **SWE-bench harness 분석 우선**: 공식 evaluation code를 먼저 분석해서, 우리 verification/recovery module이 어디에 plug-in되는지 파악. 기존 harness를 최대한 활용하고 최소한만 수정.

6. **Statistical rigor**: 각 조건당 최소 3 trials. Bootstrap confidence interval 또는 paired permutation test 사용. Effect size 보고.

7. **Terminal-Bench는 Phase 4에서**: 먼저 SWE-bench에서 결과를 확인한 뒤, best configuration만 Terminal-Bench로 검증. 두 벤치마크를 동시에 돌리지 않음.

8. **점진적 개발**: Phase 0에서 V0(no verification) baseline이 SWE-bench에서 정상 작동하는 것을 확인한 후에야 V1~V4 구현 진행.