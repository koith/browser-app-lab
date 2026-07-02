/* AIOS Kernel v0.1 — JavaScript 포트 (Python 커널과 동일 시맨틱)
   브라우저(localStorage) / Node(메모리) 양쪽에서 동작. UI 의존성 없음. */
(function (root) {
  "use strict";

  const Topics = {
    TASK_CREATED: "task.created",
    TASK_ASSIGNED: "task.assigned",
    MEETING_OPENED: "meeting.opened",
    TURN_PROPOSAL: "meeting.turn.proposal",
    TURN_CRITIQUE: "meeting.turn.critique",
    TURN_REBUTTAL: "meeting.turn.rebuttal",
    MEETING_CONCLUDED: "meeting.concluded",
    RETRO_COMPLETED: "retro.completed",
    FEEDBACK_RECEIVED: "feedback.received",
    EXPERIENCE_SAVED: "experience.saved",
    RULE_CANDIDATE: "rule.candidate.created",
    RULE_PROMOTED: "rule.promoted",
  };

  const uid = () => Math.random().toString(16).slice(2, 10) + Date.now().toString(16).slice(-4);

  /* ---------- MessageBus: 모든 모듈은 여기로만 대화한다 ---------- */
  class MessageBus {
    constructor(store) { this._subs = {}; this._store = store; }
    subscribe(topic, handler) { (this._subs[topic] ??= []).push(handler); }
    publish(topic, payload, correlationId) {
      const ev = { id: uid(), topic, payload, correlation_id: correlationId,
                   ts: new Date().toISOString() };
      if (this._store) this._store.save("events", ev);
      for (const [pat, hs] of Object.entries(this._subs)) {
        const hit = pat === "*" || pat === topic ||
          (pat.endsWith(".*") && topic.startsWith(pat.slice(0, -1)));
        if (hit) for (const h of [...hs]) h(ev);
      }
      return ev;
    }
  }

  /* ---------- Store: 문서형 저장 (localStorage 또는 메모리) ---------- */
  class Store {
    constructor(ns, backend) {
      this._ns = ns;
      this._ls = backend ?? (typeof localStorage !== "undefined" ? localStorage : null);
      this._mem = new Map();               // Node/프라이빗 모드 폴백
      this._seq = Number(this._get("__seq") || 0);
    }
    _key(kind) { return `${this._ns}:${kind}`; }
    _get(kind) { return this._ls ? this._ls.getItem(this._key(kind)) : this._mem.get(kind); }
    _set(kind, v) { this._ls ? this._ls.setItem(this._key(kind), v) : this._mem.set(kind, v); }
    _all(kind) { return JSON.parse(this._get(kind) || "{}"); }
    save(kind, obj) {
      const row = { id: uid(), ...obj, _seq: ++this._seq };
      const all = this._all(kind);
      all[row.id] = row;
      this._set(kind, JSON.stringify(all));
      this._set("__seq", String(this._seq));
      return row;
    }
    upsert(kind, row) {          // id 고정 갱신 (rule_candidates, rules)
      const all = this._all(kind);
      row._seq ??= ++this._seq;
      all[row.id] = row;
      this._set(kind, JSON.stringify(all));
      this._set("__seq", String(this._seq));
      return row;
    }
    load(kind, id) { return this._all(kind)[id] ?? null; }
    query(kind, filters = {}) {
      return Object.values(this._all(kind))
        .filter(r => Object.entries(filters).every(([k, v]) => r[k] === v))
        .sort((a, b) => (a._seq || 0) - (b._seq || 0));
    }
    wipe(kinds) { for (const k of kinds) this._set(k, "{}"); }
  }

  /* ---------- LLM 드라이버 ---------- */
  class MockLLM {
    async complete(system, prompt) {
      await 0;
      if (system.includes("의장")) return "결론: A안 채택. 근거: 토론에서 핵심 반론이 해소됨.";
      if (system.includes("회고")) return "- 근거 데이터를 회의 전에 준비한다";
      if (prompt.includes("[proposal]")) return "제안: A안을 추천한다. 근거: 타깃 적합성.";
      if (prompt.includes("[critique]")) return "반론: 근거 데이터가 부족하다.";
      if (prompt.includes("[rebuttal]")) return "재반론: 보조 데이터로 보완 가능하다.";
      return "의견: 특이사항 없음.";
    }
  }

  class ClaudeLLM {
    constructor(apiKey, model = "claude-sonnet-4-6") { this._k = apiKey; this._m = model; }
    async complete(system, prompt) {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": this._k,
          "anthropic-version": "2023-06-01",
          "anthropic-dangerous-direct-browser-access": "true",
        },
        body: JSON.stringify({
          model: this._m, max_tokens: 300, system,
          messages: [{ role: "user", content: prompt }],
        }),
      });
      if (!res.ok) throw new Error(`Claude API ${res.status}: ${await res.text()}`);
      const data = await res.json();
      return data.content.filter(b => b.type === "text").map(b => b.text).join("");
    }
  }

  /* ---------- 회고 교훈 추출: 마크다운 노이즈·구분선·껍데기 제거 ---------- */
  function extractLessons(raw){
    return String(raw).split("\n")
      .map(l => l
        .replace(/^[\s>*#·▸►◦・\-–—]+/, "") // 앞쪽 마크다운/불릿 기호
        .replace(/^\d+[.)]\s*/, "")          // "1. " 번호
        .replace(/[*`_#|]/g, "")             // 인라인 마크다운
        .replace(/^[\p{Emoji_Presentation}\p{Extended_Pictographic}\uFE0F\s]+/u, "") // 앞 이모지
        .trim())
      .filter(l => {
        if (l.length < 8) return false;                 // 껍데기
        if (/^[-–—─=~.\s]+$/.test(l)) return false;     // 구분선
        if (!/[가-힣]/.test(l)) return false;            // 한글 문장 아님
        if (/(정리|진행자|목록|머리말)$/.test(l)) return false;  // "~정리" 같은 제목 조각
        if (/^(다음에도|반복할|하지\s?말|이번|교훈|회고)/.test(l)
            && l.length < 16) return false;             // 머리말 조각
        if (!/(다|한다|하라|자|것|기|음)$/.test(l)) return false; // 완결 문장만
        return true;
      })
      .slice(0, 3);
  }

  /* ---------- 교훈 정규화 (v0.1: 사전, v0.2: LLM 드라이버) ---------- */
  function defaultNormalizer(text) {
    const table = {
      "제목이 너무 길다": ["제목은 짧고 명확하게 유지한다", "기획 AI"],
      "근거가 부족하다": ["모든 제안에는 데이터 근거를 첨부한다", "org"],
    };
    return table[text.trim()] ?? [`교훈: ${text.trim()}`, "org"];
  }

  /* ---------- Kernel ---------- */
  function createKernel({ store, llm, threshold = 3, maxRounds = 2,
                          normalizer = defaultNormalizer, turnDelay = 0 } = {}) {
    store ??= new Store("aios");
    llm ??= new MockLLM();
    const bus = new MessageBus(store);
    const agents = new Map();
    const tasks = new Map();
    const sleep = ms => new Promise(r => setTimeout(r, ms));

    /* Rule Engine — Rule의 유일한 생성 경로 */
    const normKey = t => "cand_" + t.replace(/\s+/g, "").slice(0, 64);
    bus.subscribe(Topics.EXPERIENCE_SAVED, ev => {
      const { lesson, scope, experience_id } = ev.payload;
      const key = normKey(lesson);
      const cand = store.load("rule_candidates", key) ??
        { id: key, normalized_text: lesson, count: 0, evidence: [], scope };
      cand.count += 1;
      cand.evidence.push(experience_id);
      store.upsert("rule_candidates", cand);
      bus.publish(Topics.RULE_CANDIDATE,
        { text: cand.normalized_text, count: cand.count, threshold, scope: cand.scope },
        ev.correlation_id);
      if (cand.count >= threshold) {
        const rule = { id: uid(), text: cand.normalized_text, scope: cand.scope,
                       origin: [...cand.evidence], active: 1 };
        store.upsert("rules", rule);
        cand.count = 0;
        store.upsert("rule_candidates", cand);
        bus.publish(Topics.RULE_PROMOTED,
          { rule_id: rule.id, text: rule.text, scope: rule.scope }, ev.correlation_id);
      }
    });
    const rulesFor = role =>
      store.query("rules", { active: 1 }).filter(r => r.scope === role || r.scope === "org");

    /* Experience Engine — 피드백/회고 → 교훈 */
    const emitExperience = (taskId, lesson, origin, scope) => {
      const exp = store.save("experiences", { task_id: taskId, lesson, origin, scope });
      bus.publish(Topics.EXPERIENCE_SAVED,
        { experience_id: exp.id, task_id: taskId, lesson, origin, scope }, taskId);
    };
    bus.subscribe(Topics.FEEDBACK_RECEIVED, ev => {
      store.save("feedback", ev.payload);
      const [lesson, scope] = normalizer(ev.payload.text);
      emitExperience(ev.payload.task_id, lesson, "feedback", scope);
    });
    bus.subscribe(Topics.RETRO_COMPLETED, ev => {
      for (const l of ev.payload.lessons ?? [])
        emitExperience(ev.payload.task_id, l, "retro", "org");
    });

    /* Agent — Orchestrator가 turn을 줄 때만 act() */
    function makeAgent({ name, role, goal, system, capabilities }) {
      return {
        name, role, goal, system, capabilities, shortMem: [],
        async act(turnType, context) {
          const rules = rulesFor(role).map(r => r.text);
          const exps = store.query("experiences")
            .filter(e => e.scope === role || e.scope === "org")
            .slice(-3).map(e => e.lesson);
          const prompt =
            `[${turnType}] ${system}\n\n[역할] ${role}\n[목표] ${goal}\n` +
            `[조직 규칙 — 반드시 준수]\n${rules.map(r => "- " + r).join("\n") || "- (없음)"}\n` +
            `[관련 기억]\n${[...exps, ...this.shortMem.slice(-3)].map(m => "- " + m).join("\n") || "- (없음)"}\n\n` +
            `[안건]\n${context}`;
          const text = await llm.complete(`You are ${name}.`, prompt);
          this.shortMem.push(`(${turnType}) ${text}`);
          return { agent_name: name, turn_type: turnType, content: text };
        },
      };
    }

    /* Meeting Orchestrator = 스케줄러 (제안→반론→재반론→결론) */
    async function convene(task, members) {
      const m = { id: uid(), task_id: task.id, turns: [],
                  participants: members.map(a => a.name) };
      bus.publish(Topics.MEETING_OPENED,
        { meeting_id: m.id, participants: m.participants }, task.id);
      const transcript = () =>
        m.turns.map(u => `${u.agent_name}(${u.turn_type}): ${u.content}`).join("\n");
      const turn = async (agent, type, ctx) => {
        const u = await agent.act(type, ctx);
        m.turns.push(u);
        const topic = { proposal: Topics.TURN_PROPOSAL, critique: Topics.TURN_CRITIQUE,
                        rebuttal: Topics.TURN_REBUTTAL }[type];
        bus.publish(topic, { meeting_id: m.id, ...u }, task.id);
        if (turnDelay) await sleep(turnDelay);
      };

      let ctx = `${task.title} — 목표: ${task.goal}`;
      const [proposer, ...critics] = members;
      const panel = critics.length ? critics : [proposer];
      for (let r = 0; r < maxRounds; r++) {
        await turn(proposer, r === 0 ? "proposal" : "rebuttal", ctx);
        for (const c of panel) await turn(c, "critique", transcript());
        ctx = transcript();
      }

      const decision = await llm.complete(
        "당신은 회의 의장이다. 아래 발언들을 종합해 다음을 순서대로 써라. " +
        "① 최종 결정: 한 문장으로 명확히(채택/보류/기각 중 하나와 그 대상). " +
        "② 핵심 근거: 2~3개. ③ 기각된 대안: 있으면. " +
        "표나 마크다운 없이 짧은 평문으로. 추상적 미사여구 금지.",
        m.turns.map(u => `[${u.turn_type}] ${u.agent_name}: ${u.content}`).join("\n"));
      m.conclusion = { decision, policy: "chair_decides" };
      store.upsert("meetings", m);
      bus.publish(Topics.MEETING_CONCLUDED,
        { meeting_id: m.id, task_id: task.id, participants: m.participants,
          conclusion: m.conclusion, turn_count: m.turns.length }, task.id);

      /* 회고 → 경험 저장, Short → 소거(consolidate 축약판) */
      const retroText = await llm.complete(
        "당신은 회고 진행자다. 이 회의에서 '다음에도 반복할 실무 원칙'을 " +
        "완결된 평서문 한 문장씩, 최대 3개만 뽑아라. " +
        "각 줄은 반드시 동사로 끝나는 완전한 문장이어야 한다. " +
        "제목·머리말·마크다운 기호·구분선·표는 절대 쓰지 마라. " +
        "설명 없이 문장만, 한 줄에 하나씩.",
        decision);
      const lessons = extractLessons(retroText);
      bus.publish(Topics.RETRO_COMPLETED,
        { task_id: task.id, meeting_id: m.id, lessons }, task.id);
      for (const a of members) a.shortMem = [];
      task.state = "retrospected";
      task.conclusion = m.conclusion;
      store.upsert("tasks", task);
      return m;
    }

    /* KernelAPI — App(UI)에 노출되는 유일한 표면 */
    return {
      Topics, store,
      subscribe: (t, h) => bus.subscribe(t, h),
      registerAgent(spec) { const a = makeAgent(spec); agents.set(a.name, a); return a; },
      async createTask(title, goal, taskType) {
        const task = { id: uid(), title, goal, task_type: taskType, state: "created" };
        tasks.set(task.id, task);
        store.upsert("tasks", task);
        bus.publish(Topics.TASK_CREATED,
          { task_id: task.id, title, goal, task_type: taskType }, task.id);
        const members = [...agents.values()].filter(a =>
          a.capabilities.some(c => c === taskType ||
            (c.endsWith(".*") && taskType.startsWith(c.slice(0, -1))))).slice(0, 5);
        if (!members.length) throw new Error(`no agent for ${taskType}`);
        task.state = "in_meeting";
        bus.publish(Topics.TASK_ASSIGNED,
          { task_id: task.id, agents: members.map(a => a.name) }, task.id);
        await convene(task, members);
        return task;
      },
      submitFeedback(taskId, source, text) {
        bus.publish(Topics.FEEDBACK_RECEIVED,
          { task_id: taskId, source, text }, taskId);
      },
      rulesFor,
      candidates: () => store.query("rule_candidates").filter(c => c.count > 0),
      deactivate(ruleId) {
        const r = store.load("rules", ruleId);
        if (r) { r.active = 0; store.upsert("rules", r); }
      },
    };
  }

  const AIOS = { createKernel, MockLLM, ClaudeLLM, Store, Topics };
  if (typeof module !== "undefined" && module.exports) module.exports = AIOS;
  else root.AIOS = AIOS;
})(typeof globalThis !== "undefined" ? globalThis : this);
