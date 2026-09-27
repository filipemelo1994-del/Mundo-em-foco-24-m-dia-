// Rodar: node --test tests/claude-review.test.mjs   (Node 22+, sem dependências)
import test from "node:test";
import assert from "node:assert/strict";
import { createHandler, sign, redact, enforceRules, nextAction, validateSchema, newLedger, newTask, LEDGER_PATH } from "../netlify/functions/lib/review-core.mjs";
import responseSchema from "../schemas/claude-review-response.v1.json" with { type: "json" };

const NOW = new Date("2026-09-26T22:00:00Z");
const ENV = {
  ANTHROPIC_API_KEY: "sk-ant-TESTKEY-1234567890abcdef",
  CLAUDE_REVIEW_MODEL: "modelo-de-teste-configuravel",
  CLAUDE_REVIEW_KEY: "chave-compartilhada",
  CLAUDE_REVIEW_HMAC_SECRET: "segredo-hmac",
};
const OK_REVIEW = {
  status: "OK", problem: "Nenhum problema encontrado.", probable_cause: "n/a", evidence: ["Arte confere com a pauta."],
  suggested_fix: { type: "none", reversible: true }, risk: "baixo", publish: "SIM", confidence: 0.9,
  visual_checks: [{ check: "logo sem deformação", result: "pass" }],
};
const BAD_REVIEW = { ...OK_REVIEW, status: "ERRO", problem: "Template puro publicado.", publish: "NAO", suggested_fix: { type: "code_patch", files: ["scripts/build_news_art.py"], reversible: true } };

function memoryStore(seed = {}) {
  const files = new Map(Object.entries(seed).map(([p, text]) => [p, { text, v: 1 }]));
  const store = {
    files, puts: 0, failNextPuts: 0,
    async get(path) { const f = files.get(path); return f ? { text: f.text, sha: `sha${f.v}` } : null; },
    async put(path, text, sha) {
      store.puts++;
      if (store.failNextPuts > 0) { store.failNextPuts--; return { ok: false, conflict: true }; }
      const f = files.get(path);
      if ((f && sha !== `sha${f.v}`) || (!f && sha)) return { ok: false, conflict: true };
      files.set(path, { text, v: f ? f.v + 1 : 1 });
      return { ok: true };
    },
    ledger() { return JSON.parse(files.get(LEDGER_PATH).text); },
  };
  return store;
}

// Anthropic simulada: cada item da fila é um status HTTP + corpo, ou uma função.
function fakeAnthropic(queue) {
  const calls = [];
  const impl = async (url, init) => {
    calls.push({ url, init, body: JSON.parse(init.body) });
    const next = queue.length > 1 ? queue.shift() : queue[0];
    if (typeof next === "function") return next(init);
    const { status = 200, input, headers = {} } = next;
    if (status !== 200) return new Response("{}", { status, headers });
    return new Response(JSON.stringify({ model: "modelo-servido", usage: { input_tokens: 10, output_tokens: 5 }, content: [{ type: "tool_use", name: "submit_review", input }] }), { status: 200 });
  };
  impl.calls = calls;
  return impl;
}

function setup({ anthropic, store = memoryStore(), env = ENV } = {}) {
  const sleeps = [];
  const handler = createHandler({ env, store, fetch: anthropic, now: () => NOW, sleep: async (ms) => { sleeps.push(ms); }, random: () => 0 });
  return { handler, store, sleeps };
}

const baseReq = (over = {}) => ({
  schema_version: "1.0", request_id: "rq_test_0001", task_id: "baile-da-brota-teste.arte_feed", news_id: "baile-da-brota-teste",
  round: 1, trigger: "falha_consecutiva", stage: "arte_feed", requested_by: "workflow",
  context: { validator_report: { passed: true, checks: [{ id: "dimensions", result: "pass" }] } },
  question: "A arte confere?", ...over,
});

function post(handler, body, { env = ENV, ts = NOW.getTime() / 1000, key = env.CLAUDE_REVIEW_KEY, badSig = false } = {}) {
  const raw = typeof body === "string" ? body : JSON.stringify(body);
  const headers = {
    "x-review-key": key, "x-review-timestamp": String(ts),
    "x-review-signature": badSig ? "0".repeat(64) : sign(env.CLAUDE_REVIEW_HMAC_SECRET, String(ts), raw),
  };
  return handler(new Request("https://x.test/.netlify/functions/claude-review", { method: "POST", headers, body: raw }));
}
const readJson = async (res) => res.json();

test("GET é recusado", async () => {
  const { handler } = setup({ anthropic: fakeAnthropic([{ input: OK_REVIEW }]) });
  assert.equal((await handler(new Request("https://x.test/", { method: "GET" }))).status, 405);
});

test("sem configuração completa: 500 not_configured, só nomes, nunca valores", async () => {
  const anthropic = fakeAnthropic([{ input: OK_REVIEW }]);
  const { handler } = setup({ anthropic, env: { ...ENV, CLAUDE_REVIEW_MODEL: "" } });
  const res = await post(handler, baseReq());
  const body = await readJson(res);
  assert.equal(res.status, 500);
  assert.deepEqual(body.missing, ["CLAUDE_REVIEW_MODEL"]);
  assert.equal(JSON.stringify(body).includes("sk-ant"), false);
  assert.equal(anthropic.calls.length, 0);
});

test("autenticação: chave errada, assinatura errada e timestamp antigo => 401", async () => {
  const anthropic = fakeAnthropic([{ input: OK_REVIEW }]);
  const { handler } = setup({ anthropic });
  assert.equal((await post(handler, baseReq(), { key: "errada" })).status, 401);
  assert.equal((await post(handler, baseReq(), { badSig: true })).status, 401);
  assert.equal((await post(handler, baseReq(), { ts: NOW.getTime() / 1000 - 4000 })).status, 401);
  assert.equal(anthropic.calls.length, 0);
});

test("schema: campo extra, trigger inválido e task_id fora da convenção => 400", async () => {
  const { handler } = setup({ anthropic: fakeAnthropic([{ input: OK_REVIEW }]) });
  assert.equal((await post(handler, "{nao-e-json")).status, 400);
  assert.equal((await post(handler, baseReq({ extra: 1 }))).status, 400);
  assert.equal((await post(handler, baseReq({ trigger: "qualquer" }))).status, 400);
  const res = await post(handler, baseReq({ task_id: "outra-noticia.arte_feed" }));
  assert.equal(res.status, 400);
  assert.match(JSON.stringify(await readJson(res)), /news_id/);
});

test("rodada 1: parecer, modelo vem de CLAUDE_REVIEW_MODEL, ledger e arquivo gravados", async () => {
  const anthropic = fakeAnthropic([{ input: OK_REVIEW }]);
  const { handler, store } = setup({ anthropic });
  const res = await post(handler, baseReq());
  const body = await readJson(res);
  assert.equal(res.status, 200);
  assert.equal(body.decision, "REVIEWED");
  assert.equal(body.claude_called, true);
  assert.equal(body.advisory_only, true);
  assert.equal(body.round, 1);
  assert.equal(body.rounds_used, 1);
  assert.equal(body.rounds_remaining, 1);
  assert.equal(body.next_action, "PUBLISH_IF_VALIDATOR_PASSES");
  assert.equal(anthropic.calls[0].body.model, ENV.CLAUDE_REVIEW_MODEL);
  assert.equal(anthropic.calls[0].init.headers["x-api-key"], ENV.ANTHROPIC_API_KEY);
  assert.equal(anthropic.calls[0].body.tool_choice.name, "submit_review");
  assert.deepEqual(validateSchema(responseSchema, body), []);
  const task = store.ledger().tasks["baile-da-brota-teste.arte_feed"];
  assert.equal(task.rounds_used, 1);
  assert.equal(task.requests.rq_test_0001.status, "done");
  assert.ok(store.files.has("data/reviews/baile-da-brota-teste.arte_feed-r1.json"));
});

test("idempotência: mesmo request_id devolve CACHED sem chamar Claude nem consumir rodada", async () => {
  const anthropic = fakeAnthropic([{ input: OK_REVIEW }]);
  const { handler, store } = setup({ anthropic });
  await post(handler, baseReq());
  const again = await readJson(await post(handler, baseReq()));
  assert.equal(again.decision, "CACHED");
  assert.equal(again.claude_called, false);
  assert.equal(anthropic.calls.length, 1);
  assert.equal(store.ledger().tasks["baile-da-brota-teste.arte_feed"].rounds_used, 1);
});

test("max_review_rounds = 2: a terceira tentativa vira HUMAN_REVIEW_REQUIRED sem chamar Claude", async () => {
  const anthropic = fakeAnthropic([{ input: OK_REVIEW }]);
  const { handler, store } = setup({ anthropic });
  await post(handler, baseReq({ request_id: "rq_test_0001" }));
  await post(handler, baseReq({ request_id: "rq_test_0002", round: 2 }));
  assert.equal(anthropic.calls.length, 2);
  const third = await readJson(await post(handler, baseReq({ request_id: "rq_test_0003", round: 3 })));
  assert.equal(third.decision, "HUMAN_REVIEW_REQUIRED");
  assert.equal(third.blocked_reason, "rounds_exhausted");
  assert.equal(third.claude_called, false);
  assert.equal(third.next_action, "HUMAN_REVIEW_REQUIRED");
  assert.equal(anthropic.calls.length, 2);
  assert.equal(store.ledger().tasks["baile-da-brota-teste.arte_feed"].state, "HUMAN_REVIEW_REQUIRED");
});

test("rodada 2 sem aprovação já marca HUMAN_REVIEW_REQUIRED", async () => {
  const anthropic = fakeAnthropic([{ input: BAD_REVIEW }]);
  const { handler, store } = setup({ anthropic });
  const r1 = await readJson(await post(handler, baseReq({ request_id: "rq_test_0001" })));
  assert.equal(r1.next_action, "APPLY_FIX_AND_REVALIDATE");
  const r2 = await readJson(await post(handler, baseReq({ request_id: "rq_test_0002", round: 2 })));
  assert.equal(r2.next_action, "HUMAN_REVIEW_REQUIRED");
  assert.equal(store.ledger().tasks["baile-da-brota-teste.arte_feed"].state, "HUMAN_REVIEW_REQUIRED");
});

test("falha de transporte (503) não consome rodada; 3 falhas => HUMAN_REVIEW_REQUIRED", async () => {
  const anthropic = fakeAnthropic([{ status: 503 }]);
  const { handler, store, sleeps } = setup({ anthropic });
  const key = "baile-da-brota-teste.arte_feed";
  for (let i = 1; i <= 2; i++) {
    const body = await readJson(await post(handler, baseReq({ request_id: `rq_fail_000${i}` })));
    assert.equal(body.decision, "UNAVAILABLE");
    assert.equal(body.next_action, "RETRY_SAME");
    assert.equal(body.rounds_used, 0);
    assert.equal(store.ledger().tasks[key].transport_failures, i);
  }
  const third = await readJson(await post(handler, baseReq({ request_id: "rq_fail_0003" })));
  assert.equal(third.decision, "HUMAN_REVIEW_REQUIRED");
  assert.equal(third.blocked_reason, "transport_failures");
  assert.equal(third.rounds_used, 0);
  const callsBefore = anthropic.calls.length;
  const fourth = await readJson(await post(handler, baseReq({ request_id: "rq_fail_0004" })));
  assert.equal(fourth.decision, "HUMAN_REVIEW_REQUIRED");
  assert.equal(anthropic.calls.length, callsBefore, "bloqueada: não chama Claude");
  assert.deepEqual(sleeps.slice(0, 2), [2000, 6000], "backoff 2 s e 6 s dentro de cada tentativa");
});

test("429 com retry-after é repetido e depois dá certo, consumindo 1 rodada", async () => {
  const anthropic = fakeAnthropic([{ status: 429, headers: { "retry-after": "3" } }, { input: OK_REVIEW }]);
  const { handler, store, sleeps } = setup({ anthropic });
  const body = await readJson(await post(handler, baseReq()));
  assert.equal(body.decision, "REVIEWED");
  assert.equal(anthropic.calls.length, 2);
  assert.equal(sleeps[0], 3000);
  assert.equal(store.ledger().tasks["baile-da-brota-teste.arte_feed"].rounds_used, 1);
  assert.equal(store.ledger().tasks["baile-da-brota-teste.arte_feed"].transport_failures, 0);
});

test("erro 401 da Anthropic não é repetido e conta como falha, sem consumir rodada", async () => {
  const anthropic = fakeAnthropic([{ status: 401 }]);
  const { handler, store } = setup({ anthropic });
  const body = await readJson(await post(handler, baseReq()));
  assert.equal(body.decision, "UNAVAILABLE");
  assert.equal(anthropic.calls.length, 1);
  const task = store.ledger().tasks["baile-da-brota-teste.arte_feed"];
  assert.deepEqual([task.rounds_used, task.transport_failures], [0, 1]);
});

test("mesmo fingerprint depois de correção aplicada escala sem chamar Claude", async () => {
  const anthropic = fakeAnthropic([{ input: BAD_REVIEW }]);
  const { handler } = setup({ anthropic });
  const ctx = (extra) => ({ validator_report: { passed: false, checks: [{ id: "not_equal_to_master", result: "fail" }] }, error_fingerprint: "arte_feed:template_igual:9f2c", ...extra });
  await post(handler, baseReq({ request_id: "rq_test_0001", context: ctx({}) }));
  const second = await readJson(await post(handler, baseReq({ request_id: "rq_test_0002", round: 2, context: ctx({ applied_fix: "troquei o render" }) })));
  assert.equal(second.decision, "HUMAN_REVIEW_REQUIRED");
  assert.equal(second.blocked_reason, "repeated_fingerprint");
  assert.equal(anthropic.calls.length, 1);
});

test("mesmo request_id em andamento => 409", async () => {
  const task = { ...newTask(), rounds_used: 1, requests: { rq_test_0001: { round: 1, status: "reserved", reserved_at: NOW.toISOString(), review_file: null } } };
  const seed = { ...newLedger(), tasks: { "baile-da-brota-teste.arte_feed": task } };
  const store = memoryStore({ [LEDGER_PATH]: JSON.stringify(seed) });
  const { handler } = setup({ anthropic: fakeAnthropic([{ input: OK_REVIEW }]), store });
  assert.equal((await post(handler, baseReq())).status, 409);
});

test("teto por hora => 429", async () => {
  const seed = { ...newLedger(), hourly_cap: 1, global: { window_start: NOW.toISOString(), count: 1 } };
  const store = memoryStore({ [LEDGER_PATH]: JSON.stringify(seed) });
  const anthropic = fakeAnthropic([{ input: OK_REVIEW }]);
  const { handler } = setup({ anthropic, store });
  assert.equal((await post(handler, baseReq())).status, 429);
  assert.equal(anthropic.calls.length, 0);
});

test("conflito de gravação no ledger é repetido", async () => {
  const store = memoryStore();
  store.failNextPuts = 2;
  const { handler } = setup({ anthropic: fakeAnthropic([{ input: OK_REVIEW }]), store });
  const res = await post(handler, baseReq());
  assert.equal(res.status, 200);
  assert.equal(store.ledger().tasks["baile-da-brota-teste.arte_feed"].rounds_used, 1);
});

test("segredos são redigidos antes de ir para Claude e antes de gravar o parecer", async () => {
  const secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789";
  const anthropic = fakeAnthropic([{ input: OK_REVIEW }]);
  const { handler, store } = setup({ anthropic });
  await post(handler, baseReq({ artifacts: [{ kind: "workflow_log", excerpt: `erro ao usar token ${secret} e Bearer abcdefghijklmnop1234567890` }] }));
  assert.equal(JSON.stringify(anthropic.calls[0].body).includes(secret), false);
  assert.equal(JSON.stringify(anthropic.calls[0].body).includes("abcdefghijklmnop1234567890"), false);
  const stored = store.files.get("data/reviews/baile-da-brota-teste.arte_feed-r1.json").text;
  assert.equal(stored.includes(secret), false);
  assert.equal(redact("api_key=supersecretvalue123"), "api_key=[REDACTED]");
});

test("imagem só é enviada se o host estiver na lista permitida; texto vai marcado como não confiável", async () => {
  const anthropic = fakeAnthropic([{ input: OK_REVIEW }]);
  const { handler } = setup({ anthropic });
  await post(handler, baseReq({ artifacts: [
    { kind: "art_image", url: "https://raw.githubusercontent.com/filipemelo1994-del/Mundo-em-foco-24-m-dia-/main/public/news-art/x.jpg" },
    { kind: "source_photo", url: "https://malicioso.example/foto.jpg" },
  ] }));
  const content = anthropic.calls[0].body.messages[0].content;
  const images = content.filter((b) => b.type === "image");
  assert.equal(images.length, 1);
  assert.match(images[0].source.url, /^https:\/\/raw\.githubusercontent\.com\//);
  assert.match(content[0].text, /<untrusted_data>/);
  assert.match(content[0].text, /host não permitido/);
});

test("resposta do revisor fora do schema duas vezes => INSUFICIENTE, consome rodada, nunca SIM", async () => {
  const anthropic = fakeAnthropic([{ input: { status: "OK" } }]);
  const { handler, store } = setup({ anthropic });
  const body = await readJson(await post(handler, baseReq()));
  assert.equal(body.decision, "REVIEWED");
  assert.equal(body.review.status, "INSUFICIENTE");
  assert.equal(body.review.publish, "REVALIDAR");
  assert.equal(anthropic.calls.length, 2, "uma tentativa + um reparo");
  assert.equal(store.ledger().tasks["baile-da-brota-teste.arte_feed"].rounds_used, 1);
});

test("regras do servidor: validador reprovado força NAO; correção em workflow vira manual", () => {
  const req = baseReq({ context: { validator_report: { passed: false, checks: [] } } });
  const forced = enforceRules({ ...OK_REVIEW }, req);
  assert.equal(forced.publish, "NAO");
  const patched = enforceRules({ ...BAD_REVIEW, suggested_fix: { type: "code_patch", files: [".github/workflows/build-news-art.yml"], patch: "x", reversible: true } }, baseReq());
  assert.equal(patched.suggested_fix.type, "manual");
  assert.equal(patched.suggested_fix.patch, undefined);
  const notOk = enforceRules({ ...OK_REVIEW, status: "ATENCAO" }, baseReq());
  assert.equal(notOk.publish, "REVALIDAR");
});

test("nextAction", () => {
  assert.equal(nextAction(OK_REVIEW, 1), "PUBLISH_IF_VALIDATOR_PASSES");
  assert.equal(nextAction(BAD_REVIEW, 1), "APPLY_FIX_AND_REVALIDATE");
  assert.equal(nextAction(BAD_REVIEW, 0), "HUMAN_REVIEW_REQUIRED");
  assert.equal(nextAction({ ...BAD_REVIEW, status: "INSUFICIENTE" }, 1), "HOLD");
});
