import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from models import DigestRun, Paper, PaperBreakdown
from ranking import RankablePaper, score_paper


def seed_if_empty(db: Session) -> None:
    if db.query(Paper).count() > 0:
        return

    now = datetime.now(UTC)
    for index, item in enumerate(SEED_PAPERS):
        published_at = now - timedelta(hours=8 + index * 5)
        categories = item.get("categories", [item["primary_category"]])
        paper = Paper(
            arxiv_id=item["arxiv_id"],
            arxiv_version=item.get("arxiv_version", "v1"),
            title=item["title"],
            abstract=item["abstract"],
            authors_json=json.dumps(item["authors"]),
            primary_category=item["primary_category"],
            categories_json=json.dumps(categories),
            published_at=published_at,
            updated_at=published_at + timedelta(hours=1),
            arxiv_url=f"https://arxiv.org/abs/{item['arxiv_id']}",
            pdf_url=f"https://arxiv.org/pdf/{item['arxiv_id']}",
            raw_metadata_json=json.dumps({"seed": True}),
            is_summarized=True,
            is_saved=item.get("is_saved", False),
            score=score_paper(
                RankablePaper(
                    arxiv_id=item["arxiv_id"],
                    title=item["title"],
                    abstract=item["abstract"],
                    primary_category=item["primary_category"],
                    categories=categories,
                )
            ),
        )
        db.add(paper)
        db.flush()

        breakdown = item["breakdown"]
        db.add(
            PaperBreakdown(
                paper_id=paper.id,
                one_line_takeaway=breakdown["one_line_takeaway"],
                simple_summary=breakdown["simple_summary"],
                context=breakdown["context"],
                what_is_new=breakdown["what_is_new"],
                mechanism=breakdown["mechanism"],
                evidence=breakdown["evidence"],
                methodology_caveats_json=json.dumps(breakdown["methodology_caveats"]),
                meaningful_extensions_json=json.dumps(breakdown["meaningful_extensions"]),
                novelty_type=breakdown["novelty_type"],
                difficulty=breakdown["difficulty"],
                confidence=breakdown["confidence"],
                read_this_if=breakdown["read_this_if"],
                tags_json=json.dumps(breakdown["tags"]),
                vibe=breakdown["vibe"],
                glossary_json=json.dumps(breakdown["glossary"]),
                follow_up_questions_json=json.dumps(breakdown["follow_up_questions"]),
                model_provider="seed",
                model_name="editorial-seed-v1",
                source_basis="abstract_only",
            )
        )

    db.add(
        DigestRun(
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(minutes=58),
            status="success",
            papers_fetched=len(SEED_PAPERS),
            papers_new=len(SEED_PAPERS),
            papers_summarized=len(SEED_PAPERS),
            config_json=json.dumps({"seed": True}),
        )
    )
    db.commit()


SEED_PAPERS = [
    {
        "arxiv_id": "2606.30001",
        "title": "Quiet Tools for Long-Horizon Language Agents",
        "authors": ["Mira Chen", "Owen Halpern", "Leila Ortiz"],
        "primary_category": "cs.AI",
        "categories": ["cs.AI", "cs.CL"],
        "abstract": (
            "We introduce a planning-and-audit loop for long-horizon language agents that separates tool selection, "
            "state tracking, and post-hoc critique. The method is evaluated on simulated research workflows with "
            "strong baselines, ablations over memory size, and stress tests for tool failure. Results suggest improved "
            "task completion but reveal sensitivity to prompt formatting and evaluator choice."
        ),
        "is_saved": True,
        "breakdown": {
            "one_line_takeaway": "A promising agent-control loop improves long tasks, but its gains lean on evaluation choices.",
            "simple_summary": (
                "The paper proposes a calmer way to run language-model agents: one component plans, another tracks state, "
                "and a third audits the work before the agent commits to a next step. The idea is less about a new model "
                "and more about making tool use inspectable over many steps."
            ),
            "context": (
                "Long-horizon agents often fail because they lose track of state or compound small mistakes. This sits in "
                "the line of work that treats agents as systems with memory, tools, and self-checks rather than a single prompt."
            ),
            "what_is_new": "The claimed novelty is the separation between planning, state bookkeeping, and critique, plus ablations that test each part.",
            "mechanism": (
                "The agent writes a short plan, chooses tools against that plan, records evidence in a structured notebook, "
                "then asks a critic to flag missing evidence or contradictions before proceeding."
            ),
            "evidence": "The authors report simulated workflow experiments, baseline comparisons, memory ablations, and tool-failure stress tests.",
            "methodology_caveats": [
                "The tasks are simulated, so real research workflows may have messier tool outputs and longer dependency chains.",
                "The evaluator can change the measured win rate, which makes the headline gain less stable.",
                "Prompt formatting sensitivity suggests part of the improvement may be implementation-specific.",
            ],
            "meaningful_extensions": [
                "Run the same loop on live coding or literature-review tasks with hidden test cases.",
                "Measure how often the audit step catches errors introduced by each individual tool.",
                "Compare against a smaller model with stronger external state management.",
            ],
            "novelty_type": "systems",
            "difficulty": "intermediate",
            "confidence": "medium",
            "read_this_if": "You work on agents, tool use, or evaluation of multi-step model behavior.",
            "tags": ["agents", "tool-use", "evaluation"],
            "vibe": "A margin note that keeps asking where the evidence came from",
            "glossary": [
                {
                    "term": "long-horizon agent",
                    "definition": "An AI system that must complete a task through many dependent steps.",
                },
                {"term": "ablation", "definition": "A test that removes part of a system to see how much it matters."},
            ],
            "follow_up_questions": [
                "Does the loop still help when tools return ambiguous or stale information?",
                "Which failures are prevented by structure versus simply by spending more tokens?",
            ],
        },
    },
    {
        "arxiv_id": "2606.30002",
        "title": "Sparse Circuit Traces in Instruction-Tuned Transformers",
        "authors": ["Nadia Raman", "Theo Brooks"],
        "primary_category": "cs.LG",
        "categories": ["cs.LG", "cs.AI"],
        "abstract": (
            "This work studies sparse activation pathways in instruction-tuned transformers during multi-step reasoning. "
            "It identifies recurring circuit motifs using causal interventions and compares them across model sizes. "
            "The experiments include activation patching, synthetic controls, and robustness checks across prompt families."
        ),
        "breakdown": {
            "one_line_takeaway": "An interpretability paper maps recurring reasoning circuits, with useful interventions but narrow prompts.",
            "simple_summary": (
                "The authors look for small sets of activations that reliably matter when a transformer solves reasoning-style prompts. "
                "Instead of only visualizing attention, they intervene on activations to test whether the proposed circuits change behavior."
            ),
            "context": "Mechanistic interpretability is trying to move from attractive diagrams to causal claims about model internals.",
            "what_is_new": "The paper claims recurring sparse circuit motifs persist across several instruction-tuned model sizes.",
            "mechanism": "They trace activations during reasoning prompts, patch candidate activations between runs, and measure whether outputs shift as predicted.",
            "evidence": "Evidence includes activation patching, synthetic controls, cross-size comparisons, and prompt-family robustness checks.",
            "methodology_caveats": [
                "Prompt families are still synthetic enough that the circuits may not cover messy user tasks.",
                "Sparse traces can miss distributed mechanisms that do not localize cleanly.",
                "The abstract does not make compute cost or model-family breadth clear.",
            ],
            "meaningful_extensions": [
                "Test whether the same motifs appear in code, math, and tool-use settings.",
                "Run negative controls on prompts that should not invoke the claimed circuit.",
                "Release patching notebooks so other groups can reproduce the interventions.",
            ],
            "novelty_type": "empirical",
            "difficulty": "expert",
            "confidence": "medium",
            "read_this_if": "You care about causal interpretability rather than surface-level attention maps.",
            "tags": ["interpretability", "transformers", "activation-patching"],
            "vibe": "A desk lamp pointed directly at the model's wiring",
            "glossary": [
                {
                    "term": "activation patching",
                    "definition": "Replacing internal activations to test whether they causally affect an output.",
                },
                {
                    "term": "circuit motif",
                    "definition": "A recurring pattern of internal model components that appears to implement a behavior.",
                },
            ],
            "follow_up_questions": [
                "Do these traces survive fine-tuning on different instruction datasets?",
                "How often does the method find a clean circuit when behavior is genuinely distributed?",
            ],
        },
    },
    {
        "arxiv_id": "2606.30003",
        "title": "A Small Benchmark for Models That Admit Confusion",
        "authors": ["Priya Voss", "Eli Gardner", "Min Seo"],
        "primary_category": "cs.CL",
        "categories": ["cs.CL", "cs.AI"],
        "abstract": (
            "We present a benchmark measuring whether language models can identify underspecified questions and ask for clarification. "
            "The dataset covers consumer, medical-adjacent, legal-adjacent, and technical help scenarios. We evaluate frontier and open models, "
            "finding that many systems answer confidently when the prompt lacks necessary information."
        ),
        "breakdown": {
            "one_line_takeaway": "A useful benchmark asks whether models know when to pause, though its scenario design needs scrutiny.",
            "simple_summary": (
                "The benchmark tests a behavior that normal accuracy scores often miss: whether a model notices that a question is missing "
                "key facts and asks a clarifying question instead of filling in the blanks."
            ),
            "context": "As assistants are used in higher-stakes settings, calibrated uncertainty and clarification become product and safety requirements.",
            "what_is_new": "The contribution is a curated dataset of underspecified prompts plus a scoring rubric for clarification behavior.",
            "mechanism": "Models are prompted with ambiguous requests, then judged on whether they answer, ask for missing details, or hedge without resolving the gap.",
            "evidence": "The paper reports evaluations across frontier and open models and breaks errors down by scenario type.",
            "methodology_caveats": [
                "Benchmark-only work depends heavily on whether the prompts represent real user ambiguity.",
                "Rubric-based judgments may reward formulaic clarification rather than useful help.",
                "Medical- and legal-adjacent examples need careful boundaries to avoid overclaiming safety relevance.",
            ],
            "meaningful_extensions": [
                "Validate prompts against real support logs with privacy-preserving sampling.",
                "Test multi-turn follow-up quality after the first clarification question.",
                "Measure whether models can distinguish harmless ambiguity from safety-critical ambiguity.",
            ],
            "novelty_type": "benchmark",
            "difficulty": "beginner",
            "confidence": "medium",
            "read_this_if": "You evaluate assistants or care about refusal, hedging, and clarification behavior.",
            "tags": ["benchmark", "uncertainty", "nlp"],
            "vibe": "A sticky note that says: ask one better question first",
            "glossary": [
                {
                    "term": "underspecified prompt",
                    "definition": "A request that lacks information needed for a reliable answer.",
                },
                {"term": "rubric", "definition": "A scoring guide used to judge model responses consistently."},
            ],
            "follow_up_questions": [
                "Does clarification improve final-task success or only the first-turn score?",
                "Can models learn to ask fewer but more useful questions?",
            ],
        },
    },
    {
        "arxiv_id": "2606.30004",
        "title": "Patchwise Diffusion Priors for Low-Label Vision Adaptation",
        "authors": ["Hana Wells", "Marco Bellini"],
        "primary_category": "cs.CV",
        "categories": ["cs.CV", "cs.LG"],
        "abstract": (
            "We use patchwise diffusion priors to adapt visual classifiers when labels are scarce. The method generates local feature-space "
            "augmentations and filters them with uncertainty estimates. Experiments cover fine-grained recognition and medical-imaging-like "
            "benchmarks, with ablations over patch size and filtering thresholds."
        ),
        "breakdown": {
            "one_line_takeaway": "Diffusion-generated feature patches help low-label vision adaptation, but domain realism is the pressure point.",
            "simple_summary": (
                "The paper uses a diffusion model not to create whole images, but to propose plausible local feature variations. "
                "Those patches become extra training signal when the classifier has only a small number of labels."
            ),
            "context": "Vision adaptation with few labels often relies on augmentation; diffusion priors offer richer but riskier synthetic variation.",
            "what_is_new": "The claimed novelty is patch-level feature augmentation with uncertainty filtering.",
            "mechanism": "A diffusion prior samples feature patches, an uncertainty filter rejects suspicious patches, and the classifier trains on the remaining augmented features.",
            "evidence": "Experiments include fine-grained and medical-imaging-like benchmarks plus ablations on patch size and filtering thresholds.",
            "methodology_caveats": [
                "Medical-imaging-like benchmarks may not reflect clinical distribution shifts.",
                "Synthetic patches can create shortcuts if the uncertainty filter is poorly calibrated.",
                "The abstract does not clarify whether the diffusion prior saw related data during pretraining.",
            ],
            "meaningful_extensions": [
                "Test on a real external validation set from a different acquisition pipeline.",
                "Audit whether rejected patches correspond to clinically or semantically meaningful artifacts.",
                "Compare against simpler feature-space mixup under equal compute.",
            ],
            "novelty_type": "method",
            "difficulty": "intermediate",
            "confidence": "medium",
            "read_this_if": "You work on low-label vision, augmentation, or diffusion-assisted training.",
            "tags": ["computer-vision", "diffusion", "low-label"],
            "vibe": "A soft pencil sketch sharpened into a classifier",
            "glossary": [
                {
                    "term": "diffusion prior",
                    "definition": "A generative model used as a source of plausible structure or variation.",
                },
                {
                    "term": "uncertainty filter",
                    "definition": "A rule that rejects generated samples the model judges unreliable.",
                },
            ],
            "follow_up_questions": [
                "How sensitive are gains to the pretraining data of the diffusion prior?",
                "Does patch augmentation preserve rare but important visual features?",
            ],
        },
    },
    {
        "arxiv_id": "2606.30005",
        "title": "Finite-Sample Bounds for Preference Optimization with Noisy Comparisons",
        "authors": ["Iris Valdez", "Jun Park"],
        "primary_category": "stat.ML",
        "categories": ["stat.ML", "cs.LG"],
        "abstract": (
            "We analyze preference optimization when pairwise comparisons are corrupted by annotator noise. The paper gives finite-sample "
            "bounds under margin assumptions and studies the gap between direct preference objectives and calibrated reward modeling. "
            "Synthetic experiments illustrate the tightness of the bounds."
        ),
        "breakdown": {
            "one_line_takeaway": "A theory paper clarifies when noisy preferences can still guide optimization.",
            "simple_summary": (
                "The paper asks a practical alignment question in statistical terms: if human comparisons are noisy, when can a preference "
                "optimization method still learn the intended ordering with finite data?"
            ),
            "context": "Preference data is central to post-training language models, but theory often assumes cleaner labels than real annotators provide.",
            "what_is_new": "The contribution is a finite-sample analysis under explicit noise and margin assumptions.",
            "mechanism": "The authors model pairwise comparison noise, derive error bounds, and compare direct objectives with a calibrated reward-modeling route.",
            "evidence": "Evidence is mainly theoretical, with synthetic experiments used to illustrate bound behavior.",
            "methodology_caveats": [
                "The margin assumptions may not hold for ambiguous human preferences.",
                "Synthetic experiments only weakly validate relevance to real post-training pipelines.",
                "The analysis may not capture distribution shift between preference collection and deployment.",
            ],
            "meaningful_extensions": [
                "Check the assumptions on real preference datasets with repeated annotations.",
                "Measure whether the bound predicts failures in small-scale RLHF or DPO experiments.",
                "Extend the analysis to multi-turn or context-dependent preferences.",
            ],
            "novelty_type": "theory",
            "difficulty": "expert",
            "confidence": "medium",
            "read_this_if": "You want theoretical footing for preference optimization under messy labels.",
            "tags": ["preference-optimization", "theory", "noise"],
            "vibe": "A theorem scribbled beside a coffee stain",
            "glossary": [
                {
                    "term": "finite-sample bound",
                    "definition": "A guarantee about performance with a limited amount of data.",
                },
                {
                    "term": "margin assumption",
                    "definition": "An assumption that true preferences are separated by a minimum gap.",
                },
            ],
            "follow_up_questions": [
                "How often do real preference datasets satisfy the assumed margins?",
                "Does calibrated reward modeling become preferable under specific noise regimes?",
            ],
        },
    },
    {
        "arxiv_id": "2606.30006",
        "title": "Syndrome-Aware Decoding for Biased Quantum Noise",
        "authors": ["Amara Singh", "Kaito Mori", "Elena Kovacs"],
        "primary_category": "quant-ph",
        "categories": ["quant-ph"],
        "abstract": (
            "We propose a syndrome-aware decoder for quantum error correction under biased noise. The decoder adapts to changing syndrome "
            "statistics and is evaluated in surface-code simulations across code distances and noise asymmetries. The method reduces logical "
            "error rates in regimes where dephasing dominates but adds classical decoding overhead."
        ),
        "is_saved": True,
        "breakdown": {
            "one_line_takeaway": "A quantum decoder adapts to biased noise and looks useful where dephasing dominates.",
            "simple_summary": (
                "Quantum error correction needs a classical decoder to infer likely errors from syndrome measurements. This paper makes the "
                "decoder pay attention to the current pattern of syndromes, especially when the hardware noise is not symmetric."
            ),
            "context": "Surface-code performance depends strongly on realistic noise, and many devices have biased error channels.",
            "what_is_new": "The claimed novelty is adapting the decoder to changing syndrome statistics under biased noise.",
            "mechanism": "The decoder updates its error expectations from observed syndrome patterns, then uses those expectations to choose corrections.",
            "evidence": "The authors report surface-code simulations across code distances and noise asymmetries, with logical error-rate comparisons.",
            "methodology_caveats": [
                "Simulation results depend on whether the noise model matches hardware behavior.",
                "Added classical decoding overhead could matter in real-time correction loops.",
                "The abstract does not indicate whether measurement errors and drift are fully modeled.",
            ],
            "meaningful_extensions": [
                "Benchmark latency against hardware control-cycle constraints.",
                "Test robustness when the bias changes abruptly during a run.",
                "Compare with recent neural and tensor-network decoders under identical noise models.",
            ],
            "novelty_type": "method",
            "difficulty": "expert",
            "confidence": "medium",
            "read_this_if": "You follow quantum error correction or realistic decoder design.",
            "tags": ["quantum-error-correction", "surface-code", "noise"],
            "vibe": "A careful correction written before the ink dries",
            "glossary": [
                {
                    "term": "syndrome",
                    "definition": "Measurement information used to infer what error occurred without reading the quantum state directly.",
                },
                {"term": "biased noise", "definition": "Noise where one error type is more common than another."},
            ],
            "follow_up_questions": [
                "Does the decoder still help when measurement errors dominate?",
                "Is the classical overhead compatible with near-term control hardware?",
            ],
        },
    },
    {
        "arxiv_id": "2606.30007",
        "title": "Block-Encoding Tricks for Sparse Hamiltonian Simulation",
        "authors": ["Jonas Feld", "Rina Alvarez"],
        "primary_category": "quant-ph",
        "categories": ["quant-ph", "cs.ET"],
        "abstract": (
            "This paper presents block-encoding constructions for sparse Hamiltonian simulation with improved query complexity under structured "
            "oracle access. The algorithm is analyzed asymptotically and demonstrated on toy lattice systems. The claimed speedup depends on "
            "oracle assumptions and efficient state preparation."
        ),
        "breakdown": {
            "one_line_takeaway": "A quantum algorithm improves sparse simulation on paper, but the oracle and loading assumptions carry much of the weight.",
            "simple_summary": (
                "The paper proposes a more efficient way to package a sparse Hamiltonian into a form that quantum algorithms can simulate. "
                "The mathematical improvement is interesting, but it relies on being able to query and prepare data efficiently."
            ),
            "context": "Hamiltonian simulation is a core quantum-algorithm primitive, and sparse structure is one route to better asymptotic scaling.",
            "what_is_new": "The claimed novelty is a block-encoding construction with improved query complexity under structured access.",
            "mechanism": "The algorithm uses oracles to access sparse matrix entries, builds a block-encoding, and then applies simulation routines to the encoded operator.",
            "evidence": "The evidence is asymptotic analysis plus toy lattice-system demonstrations.",
            "methodology_caveats": [
                "Oracle assumptions may hide costs that dominate in practical settings.",
                "Toy systems do not show whether constants or state preparation costs erase the advantage.",
                "The abstract does not discuss fault-tolerant resource estimates.",
            ],
            "meaningful_extensions": [
                "Include end-to-end resource estimates with state preparation and error correction overhead.",
                "Test whether the construction helps on chemistry or materials Hamiltonians with realistic sparsity.",
                "Compare constants against simpler simulation methods for small and medium problem sizes.",
            ],
            "novelty_type": "theory",
            "difficulty": "expert",
            "confidence": "medium",
            "read_this_if": "You track quantum algorithms and care about assumptions behind asymptotic speedups.",
            "tags": ["quantum-algorithms", "hamiltonian-simulation", "block-encoding"],
            "vibe": "A crisp asymptotic proof with a footnote worth circling",
            "glossary": [
                {"term": "block-encoding", "definition": "A way to embed a matrix inside a larger unitary operation."},
                {
                    "term": "oracle access",
                    "definition": "An assumption that an algorithm can query data through an idealized black-box operation.",
                },
            ],
            "follow_up_questions": [
                "What is the full cost when state preparation is included?",
                "Does the advantage persist after fault-tolerant overheads?",
            ],
        },
    },
    {
        "arxiv_id": "2606.30008",
        "title": "Retrieval-Calibrated Pretraining for Multimodal Scientific Models",
        "authors": ["Samira Holt", "Diego Marin", "Aya Nakanishi"],
        "primary_category": "cs.LG",
        "categories": ["cs.LG", "cs.CL", "cs.CV"],
        "abstract": (
            "We study multimodal pretraining with retrieval-calibrated objectives for scientific figures, captions, and text. The approach "
            "adds hard negative retrieval during pretraining and evaluates on figure question answering, caption grounding, and cross-modal search. "
            "Ablations suggest the retrieval signal improves grounding but can reduce performance on generic visual tasks."
        ),
        "breakdown": {
            "one_line_takeaway": "Retrieval pressure appears to improve scientific grounding, with a tradeoff against generic vision performance.",
            "simple_summary": (
                "The model is trained on scientific text and figures while also learning to retrieve the right evidence. That retrieval pressure "
                "is meant to make the model connect captions, diagrams, and explanations more faithfully."
            ),
            "context": "Scientific multimodal models need more than image recognition; they must ground answers in figures, captions, and surrounding text.",
            "what_is_new": "The claimed novelty is adding hard negative retrieval directly into multimodal pretraining for scientific material.",
            "mechanism": "During training, the model sees close-but-wrong figure/text pairs and is pushed to select the correctly grounded match.",
            "evidence": "The authors evaluate figure QA, caption grounding, cross-modal search, and ablations of the retrieval signal.",
            "methodology_caveats": [
                "Scientific datasets can leak near-duplicate figures across splits if curation is loose.",
                "A drop on generic visual tasks suggests specialization may be costly.",
                "The abstract does not clarify whether retrieval quality improves factual answer faithfulness.",
            ],
            "meaningful_extensions": [
                "Audit train/test overlap at the figure and paper level.",
                "Measure citation-grounded answer faithfulness, not only retrieval metrics.",
                "Test transfer to unfamiliar scientific domains such as materials or quantum hardware papers.",
            ],
            "novelty_type": "method",
            "difficulty": "intermediate",
            "confidence": "medium",
            "read_this_if": "You build scientific assistants, multimodal models, or retrieval-grounded systems.",
            "tags": ["multimodal", "retrieval", "scientific-ai"],
            "vibe": "An index card linking every diagram back to its source",
            "glossary": [
                {
                    "term": "hard negative",
                    "definition": "A wrong example that is intentionally similar to the correct one.",
                },
                {"term": "grounding", "definition": "Tying a model answer to the source evidence it depends on."},
            ],
            "follow_up_questions": [
                "Does retrieval calibration reduce hallucinated scientific claims?",
                "How much generic capability is lost when the model specializes?",
            ],
        },
    },
]
