/**
 * 齐鲁云采加密接口本地解密（对齐 verify-code/js/getDate.js）
 * 用法: node decode.js <url> '<paramsJson>' [POST|GET] [access_token]
 * 成功时只向 stdout 打印 JSON；失败非 0 退出并写 stderr。
 */
const fs = require("fs");
const axios = require("axios");
const l = require("./526b");
const CryptoJS = require("crypto-js");
const base64 = require("crypto-js/enc-base64");

const PUB_KEY =
  "043cecb117b6866ef44bf126bbbbf3b7b9d01c4c4bb0bc1bc8f55b13ceeaf4248bd8094a084484f13265e3337f25bb088767b7d775afefae4a31472de214328d76";

function stripCtrl(e) {
  return e.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "");
}

function aesPriKey(priKey) {
  const t = base64.parse(priKey);
  const key = CryptoJS.enc.Utf8.parse("WAL%15G$ja%vv^%_");
  const iv = CryptoJS.enc.Utf8.parse("9Qfcffshpl*xNWuL");
  const decrypted = CryptoJS.AES.decrypt({ ciphertext: t }, key, {
    iv,
    mode: CryptoJS.mode.CBC,
    padding: CryptoJS.pad.NoPadding,
  });
  return CryptoJS.enc.Utf8.stringify(decrypted);
}

function sm2Decrypt(cipher, key) {
  let e = cipher;
  if (e != null && e.slice(0, 2) === "04") e = e.substring(2);
  return l.doDecrypt(e, key, 1);
}

// axios 会把 HTTPS_PROXY 交给 https-proxy-agent。socks5h 不是 HTTP 代理，
// 请求既不建立连接也不报错，事件循环空转后进程以 0 退出，调用方只看到空输出。
let _socksAgent;
function socksAgent() {
  if (_socksAgent !== undefined) return _socksAgent;
  const proxyUrl = [
    "NOTICE_HTTP_PROXY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "ALL_PROXY",
    "https_proxy",
    "http_proxy",
    "all_proxy",
  ]
    .map((key) => (process.env[key] || "").trim())
    .find(Boolean);
  if (!proxyUrl || !/^socks/i.test(proxyUrl)) {
    _socksAgent = null;
    return null;
  }
  const { SocksProxyAgent } = require("socks-proxy-agent");
  _socksAgent = new SocksProxyAgent(proxyUrl);
  return _socksAgent;
}

function withNet(opts) {
  const agent = socksAgent();
  if (!agent) return opts;
  return { ...opts, httpAgent: agent, httpsAgent: agent, proxy: false };
}

async function decrypt(url, params, method, accessToken) {
  const headers = {
    "content-type": "application/json",
    sitecode: "sdzfcg",
    regionguid: "1487001",
    regioncode: "370001",
    origin: "https://ggzyjyzx.shandong.gov.cn:8182",
    referer: "https://ggzyjyzx.shandong.gov.cn:8182/gpmall-main-web/basic/supplierLibrary",
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  };
  if (accessToken) {
    headers.access_token = accessToken;
    headers.cookie = `siteCode=sdzfcg; regionguid=1487001; regioncode=370001; access_token=${accessToken}`;
  }

  const data = await axios.request(
    withNet({
      url,
      method,
      params,
      data: params,
      headers,
      timeout: 60000,
    })
  );
  if (!data.data || !data.data.data || !data.data.requestId) {
    throw new Error(`上游响应异常: ${JSON.stringify(data.data).slice(0, 200)}`);
  }

  const timeRes = await axios.get(
    "https://ggzyjyzx.shandong.gov.cn:8182/gpmall-basic/api/v1/ignore/time",
    withNet({ params: { _t: Date.now() }, headers, timeout: 30000 })
  );
  const priParams = {
    accessKeyId: "wr$vW6_%E0~zM!JsUp4T",
    accessKeySecret: "cLGSNAUFQTvBQQ_Zyi5K",
    uri: "/api/v1/pri",
    timestamp: timeRes.data.data,
  };
  const accessKey = "04" + l.doEncrypt(JSON.stringify(priParams), PUB_KEY);
  const priRes = await axios.post(
    "https://ggzyjyzx.shandong.gov.cn:8182/gpmall-basic/api/v1/pri",
    { accessKey, requestId: data.data.requestId },
    withNet({ headers, timeout: 30000 })
  );
  if (!priRes.data || !priRes.data.data) {
    throw new Error(
      `pri 失败: ${priRes.data && priRes.data.message ? priRes.data.message : JSON.stringify(priRes.data).slice(0, 200)}`
    );
  }
  const plain = sm2Decrypt(data.data.data, stripCtrl(aesPriKey(priRes.data.data)));
  return JSON.parse(plain);
}

(async () => {
  const url = process.argv[2];
  const paramsRaw = process.argv[3];
  const method = (process.argv[4] || "POST").toUpperCase();
  const token = process.argv[5] || process.env.SD_ACCESS_TOKEN || "";
  if (!url || !paramsRaw) {
    console.error("usage: node decode.js <url> '<paramsJson>' [METHOD] [access_token]");
    process.exit(2);
  }
  try {
    const result = await decrypt(url, JSON.parse(paramsRaw), method, token);
    // 同步写 fd，避免进程退出时把管道里的 JSON 丢掉
    fs.writeSync(1, JSON.stringify(result));
  } catch (e) {
    const msg = (e && (e.stack || e.message)) || String(e);
    fs.writeSync(2, `${msg}\n`);
    process.exit(1);
  }
})();
