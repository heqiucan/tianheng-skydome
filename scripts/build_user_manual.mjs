// Documentation-only renderer; uses bundled marked (MIT), no product dependency changes.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const markedModule = process.env.MARKED_MODULE;
if (!markedModule) throw new Error('Set MARKED_MODULE to the installed marked/lib/marked.esm.js path.');
const { marked } = await import(pathToFileURL(markedModule).href);
const source = path.join(root, 'docs', '天亨SKYDOME使用手册.md');
const markdown = await fs.readFile(source, 'utf8');
const escape = value => value.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
let body = marked.parse(markdown.replace(/^# .+\n/, ''), { gfm: true });
const sections = [];
body = body.replace(/<h2>(.*?)<\/h2>/g, (_, heading) => {
  const id = `section-${String(sections.length + 1).padStart(2,'0')}`;
  sections.push({ id, heading });
  return `<h2 id="${id}">${heading}</h2>`;
});
const images = [...body.matchAll(/<p><img src="([^"]+)" alt="([^"]*)"><\/p>/g)];
for (const match of images) {
  const bytes = await fs.readFile(path.join(root, 'docs', match[1]));
  body = body.replace(match[0], `<figure><img src="data:image/jpeg;base64,${bytes.toString('base64')}" alt="${match[2]}" loading="eager" width="1440" height="900"><figcaption>${match[2]} · 实际验收截图，数据以当前页面为准</figcaption></figure>`);
}
// The HTML is portable; project documentation references remain readable as file locations.
body = body.replace(/<a href="([^"#]+\.md)">(.*?)<\/a>/g, (_, href, label) => `<span>${label}（项目文档：<code>${escape(href)}</code>）</span>`);
body = body.replace(/<table>/g, '<div class="table-scroll"><table>').replace(/<\/table>/g, '</table></div>');
const toc = sections.map(s => `<a href="#${s.id}">${s.heading}</a>`).join('\n');
const html = `<!doctype html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>天亨 SKYDOME · 使用手册</title>
<style>
:root{--ink:#17304a;--sub:#50657a;--blue:#1269a3;--line:#dce5ee;--paper:#fff;--nav:#0c2035;--cyan:#63dbef}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:28px}body{margin:0;background:#edf2f7;color:var(--ink);font-family:"Microsoft YaHei","Segoe UI",sans-serif;line-height:1.85;font-size:16px}a{color:var(--blue);text-underline-offset:3px}aside{position:fixed;inset:0 auto 0 0;width:268px;background:var(--nav);color:#fff;padding:30px 22px;overflow:auto}.brand{color:var(--cyan);font-size:13px;letter-spacing:2px}.nav-title{font-size:23px;font-weight:700;line-height:1.5;margin:12px 0 22px}nav a{display:block;color:#c9d8e6;text-decoration:none;font-size:13px;padding:8px 10px;border-radius:6px;margin:2px 0}nav a:hover,nav a:focus{color:#fff;background:#183a55}.nav-note{font-size:12px;color:#90a9be;margin-top:26px}.shell{margin-left:268px;padding:32px 40px 60px;max-width:1360px}.cover{background:linear-gradient(125deg,#0b2039,#153e5c);color:#fff;border-radius:14px;padding:42px 46px;margin-bottom:22px;box-shadow:0 8px 24px #12304a12}.eyebrow{font-size:12px;letter-spacing:3px;color:var(--cyan)}h1{font-size:36px;line-height:1.4;margin:12px 0}.lead{color:#c8dae8;max-width:700px}.flow{display:flex;gap:8px;flex-wrap:wrap;margin-top:25px}.flow span{border:1px solid #3a647c;border-radius:5px;padding:5px 11px;font-size:13px;color:#e2f3fc}.toolbar{display:flex;flex-wrap:wrap;gap:10px;margin-top:24px}.toolbar a{border:1px solid #80cbec;background:#163e59;color:#edfbff;border-radius:6px;padding:8px 14px;font-size:13px;text-decoration:none}.content{background:var(--paper);padding:34px 46px;border:1px solid var(--line);border-radius:12px}h2{font-size:26px;line-height:1.5;margin:55px 0 24px;padding-top:12px;padding-bottom:14px;border-bottom:2px solid #cde4f3;color:#0e4267}h2:first-of-type{margin-top:32px}h3{font-size:19px;margin:30px 0 12px;color:#1c557b}p{margin:14px 0}li{padding-left:2px;margin:7px 0}ul,ol{padding-left:26px}strong{font-weight:700;color:#153e5d}.content>p:first-child{font-size:14px;color:var(--sub)}blockquote{margin:24px 0;padding:15px 20px;background:#edf7fc;border-left:4px solid #3096c8;border-radius:0 8px 8px 0}blockquote p{margin:5px 0}.table-scroll{overflow:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.75}th{background:#e9f2f8;text-align:left;color:#184866}th,td{padding:12px 14px;border:1px solid var(--line);vertical-align:top}tbody tr:nth-child(even){background:#f8fafc}td:first-child{min-width:130px}code{font-family:Consolas,"Microsoft YaHei",monospace;font-size:.9em;background:#eff3f7;border-radius:4px;padding:2px 5px;overflow-wrap:anywhere}pre{background:#0b2236;color:#ddf2ff;padding:17px 20px;border-radius:7px;overflow:auto}pre code{background:none;padding:0;font-size:14px}figure{margin:26px 0 30px;break-inside:avoid}figure img{display:block;width:100%;height:auto;border-radius:8px;border:1px solid #c8d5e1}figcaption{font-size:12px;color:#61758a;line-height:1.65;margin:9px 0;text-align:center}.footer{font-size:12px;color:#657b8f;text-align:center;padding:20px 0}.mobile-toc{display:none}
@media(max-width:1050px){aside{width:230px;padding:22px 16px}.shell{margin-left:230px;padding:20px}.cover,.content{padding:28px}h1{font-size:30px}}
@media(max-width:760px){aside{display:none}.shell{margin-left:0;padding:12px}.cover,.content{padding:23px 18px}h1{font-size:29px}h2{font-size:23px}.mobile-toc{display:block;background:#f1f7fb;border:1px solid var(--line);padding:12px 15px;border-radius:8px}.mobile-toc a{display:block;font-size:14px;padding:5px}table{min-width:560px}body{font-size:15px}}
@media print{@page{size:A4;margin:16mm}html{scroll-behavior:auto}body{background:white;font-size:10.5pt;color:#17304a}aside,.toolbar,.mobile-toc,.footer{display:none}.shell{margin:0;padding:0;max-width:none}.cover{border:1px solid #b3c9db;background:#f0f6fb!important;color:#14314a;box-shadow:none;border-radius:0;padding:22px;margin-bottom:20px}.eyebrow,.lead,.flow span{color:#214d70}h1{font-size:25pt}.flow span{border-color:#aec8dc}.content{border:0;padding:0}.content h2{font-size:17pt;margin-top:28px;break-after:avoid}h3{font-size:12pt;break-after:avoid}p,li{orphans:3;widows:3}table{font-size:9pt;min-width:0}th,td{padding:7px 8px}tr{break-inside:avoid}thead{display:table-header-group}.table-scroll{overflow:visible}pre{white-space:pre-wrap;color:#123;background:#edf3f8}figure img{max-height:105mm;object-fit:contain}a{color:#145b87;text-decoration:none}blockquote{break-inside:avoid}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
</style></head><body>
<aside aria-label="手册目录"><div class="brand">TIANHENG / SKYDOME</div><div class="nav-title">产品使用手册</div><nav>${toc}</nav><p class="nav-note">本地演示版 · 应用 0.5<br>2026 年 11 月 16 日<br>支持 Ctrl+P 打印或另存 PDF</p></aside>
<div class="shell"><header class="cover"><div class="eyebrow">OPERATOR GUIDE / 01</div><h1>天亨 SKYDOME Agent<br>使用手册</h1><p class="lead">从桌面启动到风险研判、协同巡检和结果回看。按真实页面操作，理解每一步的输入、结果和能力边界。</p><div class="flow"><span>感知</span><span>识别</span><span>研判</span><span>决策</span><span>调度</span><span>执行</span><span>反馈</span></div><div class="toolbar"><a href="#section-03">先看快速上手</a><a href="#section-04">完整操作流程</a><a href="data:text/markdown;charset=utf-8;base64,${Buffer.from(markdown).toString('base64')}" download="天亨SKYDOME使用手册.md">保存文字版</a></div></header>
<main class="content"><details class="mobile-toc"><summary>展开章节目录</summary>${toc}</details>${body}</main><footer class="footer">天亨 SKYDOME · 使用手册 v1.0 · 依据当前实现和既有实测记录编制</footer></div>
</body></html>`;
const outputs = [path.join(root,'docs','天亨SKYDOME使用手册.html'), path.join(root,'public','manual','index.html')];
for (const output of outputs) { await fs.mkdir(path.dirname(output), { recursive:true }); await fs.writeFile(output, html, 'utf8'); }
console.log(JSON.stringify({ sections:sections.length, images:images.length, markdownCharacters:markdown.length, htmlBytes:Buffer.byteLength(html), outputs },null,2));
