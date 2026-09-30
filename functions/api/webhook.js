// 《种子》签名墙 · Webhook (Cloudflare Pages Function)
// 接收 Web3Forms 提交 → 自动创建 GitHub Issue 供审核
//
// Webhook URL: https://seed-trilogy.pages.dev/api/webhook?secret=<WEBHOOK_SECRET>
//
// 环境变量（Cloudflare Pages → Settings → Environment variables）:
//   GITHUB_TOKEN  — 有 repo 权限的 GitHub PAT
//   WEBHOOK_SECRET — 随机密钥，防止未授权调用

const REPO_OWNER = "mianozc";
const REPO_NAME = "seed-trilogy";

export async function onRequestPost({ request, env }) {
  const url = new URL(request.url);
  const secret = url.searchParams.get("secret") || "";

  // 验证 webhook secret
  if (secret !== (env.WEBHOOK_SECRET || "5fb444b2d7d29ae1c3e726f197e77d2f")) {
    return new Response("Forbidden", { status: 403 });
  }

  let data;
  try {
    data = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  // 蜜罐字段：如果填了说明是机器人，跳过
  if (data.hp || data.Hp) {
    return Response.json({ ok: true, skipped: "honeypot" });
  }

  // 提取表单字段
  const who = (data.who || data.Who || "").trim() || "匿名";
  const kind = (data.kind || data.Kind || "").trim() || "匿名";
  const line = (data.line || data.Line || "").trim();
  const submittedAt = data.submitted_at || data["Submitted At"] || new Date().toISOString();

  if (!line) {
    return Response.json({ error: "Missing 'line' field" }, { status: 400 });
  }

  // 构造签名数据（GitHub Action 解析用）
  const sigData = {
    who,
    kind,
    line,
    createdAt: new Date(submittedAt).getTime() || Date.now(),
  };

  // 创建 GitHub Issue
  const issueBody = [
    `## 新签名待审核`,
    ``,
    `| 字段 | 内容 |`,
    `|---|---|`,
    `| 署名 | ${who} |`,
    `| 身份 | ${kind} |`,
    `| 留言 | ${line} |`,
    `| 提交时间 | ${submittedAt} |`,
    ``,
    `<!--SIGNATURE_DATA-->`,
    JSON.stringify(sigData),
    `<!--/SIGNATURE_DATA-->`,
    ``,
    `---`,
    `审核通过请添加 \`approved\` 标签，拒绝请添加 \`rejected\` 标签。`,
  ].join("\n");

  const ghRes = await fetch(
    `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/issues`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "seed-trilogy-webhook",
      },
      body: JSON.stringify({
        title: `签名审核: ${who} — "${line.slice(0, 30)}"`,
        body: issueBody,
        labels: ["pending-review"],
      }),
    }
  );

  if (!ghRes.ok) {
    const errText = await ghRes.text();
    return Response.json(
      { error: `GitHub API ${ghRes.status}`, detail: errText },
      { status: 502 }
    );
  }

  const issue = await ghRes.json();
  return Response.json({
    ok: true,
    issue_number: issue.number,
    issue_url: issue.html_url,
  });
}

// 健康检查
export async function onRequestGet({ request }) {
  return new Response("ok", { status: 200 });
}
