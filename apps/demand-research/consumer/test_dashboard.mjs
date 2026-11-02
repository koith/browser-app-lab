/** Render the shipped standalone page in a DOM sandbox without external calls. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { JSDOM, VirtualConsole } from "jsdom";

const dir = path.dirname(new URL(import.meta.url).pathname);
const html = fs.readFileSync(path.join(dir, "index.html"), "utf8");
const source = JSON.parse(fs.readFileSync(path.join(dir, "demo-report.json"), "utf8"));
const failures = [];
const vc = new VirtualConsole();
vc.on("jsdomError", e => failures.push(String(e.stack || e)));

let fetched = [];
const dom = new JSDOM(html, {
  url: "https://koith.github.io/browser-app-lab/apps/demand-research/consumer/",
  runScripts: "dangerously",
  resources: "usable",
  virtualConsole: vc,
  beforeParse(win) {
    win.fetch = async (url, options) => {
      fetched.push({url: String(url), options});
      assert.equal(String(url), "./demo-report.json");
      return {ok: true, json: async () => source};
    };
  },
});

await new Promise(resolve => setTimeout(resolve, 150));
const doc = dom.window.document;
assert.deepEqual(failures, [], "browser JavaScript errors");
assert.equal(fetched.length, 1, "the dashboard fetches exactly one demo report");
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
assert.equal(fetched.length, 1);
assert.deepEqual(failures, []);
console.log("BROWSER_DOM_QA_PASS: 4 metrics, 4 product cards, 40 evidence groups, sorting, no JS errors");
dom.window.close();
