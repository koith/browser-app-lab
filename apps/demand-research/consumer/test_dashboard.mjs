/** Render the shipped standalone page in a DOM sandbox without external calls. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { JSDOM, VirtualConsole, ResourceLoader } from "jsdom";

const dir = path.dirname(new URL(import.meta.url).pathname);
const html = fs.readFileSync(path.join(dir, "index.html"), "utf8");
const source = JSON.parse(fs.readFileSync(path.join(dir, "demo-report.json"), "utf8"));
const editorial = JSON.parse(fs.readFileSync(path.join(dir, "editorial-report.json"), "utf8"));
const editorialJS = fs.readFileSync(path.join(dir, "editorial_view.js"), "utf8");
const sessionReport = JSON.parse(fs.readFileSync(path.join(dir, "session-report.json"), "utf8"));
const sessionJS = fs.readFileSync(path.join(dir, "session_view.js"), "utf8");
const attention = JSON.parse(fs.readFileSync(path.join(dir, "attention-report.json"), "utf8"));
const attentionJS = fs.readFileSync(path.join(dir, "attention_view.js"), "utf8");
class LocalOnlyLoader extends ResourceLoader {
  fetch(url) {
    if (url.endsWith("/editorial_view.js")) return Promise.resolve(Buffer.from(editorialJS));
    if (url.endsWith("/session_view.js")) return Promise.resolve(Buffer.from(sessionJS));
    if (url.endsWith("/attention_view.js")) return Promise.resolve(Buffer.from(attentionJS));
    throw new Error("Unexpected external page resource: " + url);
  }
}
const failures = [];
const vc = new VirtualConsole();
vc.on("jsdomError", e => failures.push(String(e.stack || e)));

let fetched = [];
const dom = new JSDOM(html, {
  url: "https://koith.github.io/browser-app-lab/apps/demand-research/consumer/",
  runScripts: "dangerously",
  resources: new LocalOnlyLoader(),
  virtualConsole: vc,
  beforeParse(win) {
    win.fetch = async (url, options) => {
      fetched.push({url: String(url), options});
      if (String(url) === "./demo-report.json") return {ok: true, json: async () => source};
      if (String(url) === "./editorial-report.json") return {ok: true, json: async () => editorial};
      if (String(url) === "./session-report.json") return {ok: true, json: async () => sessionReport};
      if (String(url) === "./attention-report.json") return {ok: true, json: async () => attention};
      throw new Error("Unapproved fetch: " + String(url));
    };
  },
});

await new Promise(resolve => setTimeout(resolve, 350));
const doc = dom.window.document;
assert.deepEqual(failures, [], "browser JavaScript errors");
assert.deepEqual(fetched.map(x => x.url).sort(), ["./attention-report.json", "./demo-report.json", "./editorial-report.json", "./session-report.json"]);
assert.equal(doc.querySelectorAll(".attention-card").length, 6);
assert.equal(doc.querySelectorAll(".attention-day").length, 84);
assert.match(doc.querySelector("#attentionStatus").textContent, /실제 구매량 아님/);
assert.match(doc.querySelector("#attentionWindow").textContent, /2026-10-31/);
assert.match(doc.querySelector("#attentionCards").textContent, /PlayStation 5/);
assert.match(doc.querySelector("#attentionCards").textContent, /로봇청소기/);
assert.equal(doc.querySelectorAll(".session-stat").length, 4);
assert.match(doc.querySelector("#sessionMetrics").textContent, /12,330/);
assert.match(doc.querySelector("#sessionMetrics").textContent, /1,908/);
assert.match(doc.querySelector("#sessionMetrics").textContent, /15.47%/);
assert.match(doc.querySelector("#sessionStatus").textContent, /현재 구매 전환율/);
assert.ok(doc.querySelectorAll(".session-row").length >= 8, "historic month cohort rows");
assert.equal(doc.querySelectorAll(".editorial-stat").length, 4);
assert.equal(doc.querySelectorAll(".editorial-card").length, 36);
assert.match(doc.querySelector("#editorialMetrics").textContent, /8,107/);
assert.match(doc.querySelector("#editorialMetrics").textContent, /101/);
assert.match(doc.querySelector("#editorialStatus").textContent, /구매 수요 지표 아님/);
assert.equal(doc.querySelectorAll(".metric").length, 4);
assert.equal(doc.querySelectorAll("article.product").length, 4);
assert.match(doc.querySelector("#modeBadge").textContent, /합성 데이터/);
assert.match(doc.querySelector("#loadStatus").textContent, /4개 상품/);
assert.match(doc.querySelector("#metrics").textContent, /280/);
assert.match(doc.querySelector("#metrics").textContent, /68/);
assert.match(doc.querySelector("#products").textContent, /무선 이어폰/);
assert.equal(doc.querySelectorAll(".product details").length, 4);
assert.equal(doc.querySelectorAll(".product .evidence-card").length, 40);
assert.equal(doc.querySelector("#products").textContent.includes("C-2eec036cacae"), true);

// Client-side sorting must re-render product cards without re-fetching.
const select = doc.querySelector("#order");
select.value = "repeat";
select.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
assert.equal(doc.querySelectorAll("article.product").length, 4);
assert.equal(fetched.length, 4);
const category = doc.querySelector("#editorialCategory");
category.value = "robot-vacuums";
category.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
assert.equal(doc.querySelectorAll(".editorial-card").length, 7);
const dimension=doc.querySelector("#sessionDimension");
dimension.value="visitor";
dimension.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
assert.equal(doc.querySelectorAll(".session-row").length, 3);
dimension.value="product_pages";
dimension.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
assert.equal(doc.querySelectorAll(".session-row").length, 5);
assert.equal(fetched.length, 4);
const attentionFilter = doc.querySelector("#attentionType");
attentionFilter.value = "goods";
attentionFilter.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
assert.equal(doc.querySelectorAll(".attention-card").length, 3);
attentionFilter.value = "category";
attentionFilter.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
assert.equal(doc.querySelectorAll(".attention-card").length, 3);
assert.equal(fetched.length, 4);
assert.deepEqual(failures, []);
console.log("BROWSER_DOM_QA_PASS: 4 synthetic metrics and 40 groups; real 36 editorial products; real UCI 12330 sessions and 1908 purchases; current CC0 6 articles and 84 daily bars, filters, no JS errors");
dom.window.close();
