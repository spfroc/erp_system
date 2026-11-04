import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { CircleHelp, KeyRound, RefreshCw, Shield, Trash2, UserRound } from "lucide-react";
import { backendApiUrl } from "./apiConfig";
import { CopyableLine, PanelTitle } from "./listUi";
import type { AppData, PermissionKey, User } from "./types";

type NoticeFn = (message: string, type?: "success" | "error") => void;

const MCP_CONNECTOR_URL = "https://assist.qlyc.co/api/mcp/";
const WECOM_ADMIN_URL = "https://work.weixin.qq.com/";
const WECOM_CONNECTOR_DOC = "https://open.work.weixin.qq.com/help2/pc/21742";

interface ApiTokenInfo {
  hasToken: boolean;
  id?: string;
  name?: string;
  tokenPrefix?: string;
  createdAt?: string;
  lastUsedAt?: string;
  token?: string;
}

async function readJson(response: Response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

export function ProfileCenter({
  data,
  currentUser,
  permissions,
  permissionLabels,
  permissionGroups,
  applyUser,
  onNotice,
}: {
  data: AppData;
  currentUser: User;
  permissions: Set<PermissionKey>;
  permissionLabels: Record<PermissionKey, string>;
  permissionGroups: Array<{ title: string; keys: PermissionKey[] }>;
  applyUser: (user: User) => void;
  onNotice: NoticeFn;
}) {
  const [name, setName] = useState(currentUser.name || "");
  const [phone, setPhone] = useState(currentUser.phone || "");
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);

  const [tokenInfo, setTokenInfo] = useState<ApiTokenInfo>({ hasToken: false });
  const [freshToken, setFreshToken] = useState("");
  const [tokenBusy, setTokenBusy] = useState(false);

  const roleNames =
    currentUser.roleIds
      .map((id) => data.roles.find((role) => role.id === id)?.name)
      .filter(Boolean)
      .join("、") || "未分配角色";

  const permissionSections = useMemo(() => {
    const owned = [...permissions];
    return permissionGroups
      .map((group) => ({
        title: group.title,
        items: group.keys
          .filter((key) => permissions.has(key))
          .map((key) => ({ key, label: permissionLabels[key] || key })),
      }))
      .filter((group) => group.items.length > 0)
      .concat(
        (() => {
          const grouped = new Set(permissionGroups.flatMap((g) => g.keys));
          const extras = owned
            .filter((key) => !grouped.has(key))
            .map((key) => ({ key, label: permissionLabels[key] || key }));
          return extras.length ? [{ title: "其他", items: extras }] : [];
        })(),
      );
  }, [permissionGroups, permissionLabels, permissions]);

  useEffect(() => {
    setName(currentUser.name || "");
    setPhone(currentUser.phone || "");
  }, [currentUser.id, currentUser.name, currentUser.phone]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(backendApiUrl("/api/auth/api-token/"), { credentials: "include" });
        const payload = await readJson(response);
        if (!cancelled && response.ok) {
          setTokenInfo((payload.data as ApiTokenInfo) || { hasToken: false });
        }
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    setSavingProfile(true);
    try {
      const response = await fetch(backendApiUrl("/api/auth/profile/"), {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), phone: phone.trim() }),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "保存失败");
      }
      applyUser(payload.data as User);
      onNotice("个人信息已保存", "success");
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "保存失败", "error");
    } finally {
      setSavingProfile(false);
    }
  }

  async function savePassword(event: FormEvent) {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      onNotice("两次输入的新密码不一致", "error");
      return;
    }
    setSavingPassword(true);
    try {
      const response = await fetch(backendApiUrl("/api/auth/change-password/"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ currentPassword, newPassword, confirmPassword }),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "修改密码失败");
      }
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      onNotice("密码已更新", "success");
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "修改密码失败", "error");
    } finally {
      setSavingPassword(false);
    }
  }

  async function generateToken() {
    if (tokenInfo.hasToken && !window.confirm("重新生成后旧凭证立即失效，是否继续？")) {
      return;
    }
    setTokenBusy(true);
    try {
      const response = await fetch(backendApiUrl("/api/auth/api-token/"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "企微连接器" }),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        throw new Error(payload.detail || "生成凭证失败");
      }
      const info = payload.data as ApiTokenInfo;
      setTokenInfo(info);
      setFreshToken(info.token || "");
      onNotice("凭证已生成，请立即复制保存", "success");
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "生成凭证失败", "error");
    } finally {
      setTokenBusy(false);
    }
  }

  async function revokeToken() {
    if (!window.confirm("确定吊销当前凭证？企微连接器将无法继续使用该 Token。")) return;
    setTokenBusy(true);
    try {
      const response = await fetch(backendApiUrl("/api/auth/api-token/"), {
        method: "DELETE",
        credentials: "include",
      });
      if (!response.ok) {
        const payload = await readJson(response);
        throw new Error(payload.detail || "吊销失败");
      }
      setTokenInfo({ hasToken: false });
      setFreshToken("");
      onNotice("凭证已吊销", "success");
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "吊销失败", "error");
    } finally {
      setTokenBusy(false);
    }
  }

  return (
    <div className="stack profile-center">
      <div className="panel">
        <PanelTitle title="个人中心" subtitle="维护账号资料、登录密码，以及企微连接器个人凭证。" />
        <div className="profile-meta">
          <div>
            <em>账号 ID</em>
            <CopyableLine text={currentUser.id} label="账号 ID">
              <strong>{currentUser.id}</strong>
            </CopyableLine>
          </div>
          <div>
            <em>角色</em>
            <strong>{roleNames}</strong>
          </div>
          <div>
            <em>状态</em>
            <strong>{currentUser.status}</strong>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>
              <UserRound size={18} /> 基本信息
            </h2>
            <p>修改姓名与手机号；手机号可用于登录。</p>
          </div>
        </div>
        <form className="form-grid profile-form" onSubmit={(event) => void saveProfile(event)}>
          <label>
            姓名
            <input value={name} onChange={(event) => setName(event.target.value)} required maxLength={100} />
          </label>
          <label>
            手机号
            <input
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="11 位手机号"
              maxLength={11}
            />
          </label>
          <div className="modal-actions profile-form-actions">
            <button className="primary" type="submit" disabled={savingProfile}>
              {savingProfile ? "保存中…" : "保存资料"}
            </button>
          </div>
        </form>
      </div>

      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>
              <KeyRound size={18} /> 修改密码
            </h2>
            <p>修改后需使用新密码登录。</p>
          </div>
        </div>
        <form className="form-grid profile-form" onSubmit={(event) => void savePassword(event)}>
          <label>
            当前密码
            <input
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <label>
            新密码
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              minLength={6}
              required
            />
          </label>
          <label>
            确认新密码
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              minLength={6}
              required
            />
          </label>
          <div className="modal-actions profile-form-actions">
            <button className="primary" type="submit" disabled={savingPassword}>
              {savingPassword ? "提交中…" : "更新密码"}
            </button>
          </div>
        </form>
      </div>

      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>
              <Shield size={18} /> 连接器凭证
              <span className="profile-connector-help">
                <button type="button" className="profile-connector-help-trigger" aria-label="企微连接器配置帮助">
                  <CircleHelp size={16} />
                  配置帮助
                </button>
                <div className="profile-connector-help-panel" role="tooltip">
                  <strong>企业微信「添加连接器」怎么填</strong>
                  <ol>
                    <li>
                      打开{" "}
                      <a href={WECOM_ADMIN_URL} target="_blank" rel="noreferrer">
                        企业微信管理后台
                      </a>
                      → <em>智能专区 → 智能助理 → 连接器管理 → 添加连接器</em>。
                    </li>
                    <li>对照下方配置项填写（与企微表单字段一一对应）。</li>
                    <li>先在本页生成凭证，再把「值」整段粘贴到企微静态凭证。</li>
                  </ol>
                  <div className="profile-connector-help-links">
                    <em>配置链接</em>
                    <a href={WECOM_ADMIN_URL} target="_blank" rel="noreferrer">
                      企业微信工作台
                    </a>
                    <a href={WECOM_CONNECTOR_DOC} target="_blank" rel="noreferrer">
                      官方：智能助理如何管理连接器
                    </a>
                    <CopyableLine text={MCP_CONNECTOR_URL} label="MCP URL">
                      <code>{MCP_CONNECTOR_URL}</code>
                    </CopyableLine>
                  </div>
                  <div className="profile-connector-help-table">
                    <em>配置项（企微表单）</em>
                    <div className="profile-connector-help-row">
                      <span>连接器名称 *</span>
                      <span>任意，如「壹采助手」</span>
                    </div>
                    <div className="profile-connector-help-row">
                      <span>URL *</span>
                      <span>
                        填 <code>{MCP_CONNECTOR_URL}</code>
                        <br />
                        <small>可使用企业配置的可信域名</small>
                      </span>
                    </div>
                    <div className="profile-connector-help-row">
                      <span>静态凭证 · 键</span>
                      <span>
                        固定填 <code>Authorization</code>
                      </span>
                    </div>
                    <div className="profile-connector-help-row">
                      <span>静态凭证 · 值</span>
                      <span>
                        填本页复制的 <code>Bearer …</code>（已含前缀，勿再手写 Bearer）
                      </span>
                    </div>
                  </div>
                </div>
              </span>
            </h2>
            <p>用于企业微信智能助理 MCP 连接器。鼠标悬停「配置帮助」可查看填写对照；完整 Token 仅在生成时显示一次。</p>
          </div>
          <div className="panel-title-buttons">
            <button className="primary" type="button" disabled={tokenBusy} onClick={() => void generateToken()}>
              <RefreshCw size={15} />
              {tokenInfo.hasToken ? "重新生成" : "生成凭证"}
            </button>
            {tokenInfo.hasToken && (
              <button className="ghost danger-action" type="button" disabled={tokenBusy} onClick={() => void revokeToken()}>
                <Trash2 size={15} />
                吊销
              </button>
            )}
          </div>
        </div>

        <div className="profile-connector-fields">
          <div className="profile-connector-field">
            <em>URL（复制到企微「URL」）</em>
            <CopyableLine text={MCP_CONNECTOR_URL} label="MCP URL">
              <code>{MCP_CONNECTOR_URL}</code>
            </CopyableLine>
          </div>
          <div className="profile-connector-field">
            <em>静态凭证 · 键（复制到企微「键」）</em>
            <CopyableLine text="Authorization" label="凭证键">
              <code>Authorization</code>
            </CopyableLine>
          </div>
          <div className="profile-connector-field">
            <em>静态凭证 · 值（复制到企微「值」）</em>
            {freshToken ? (
              <CopyableLine text={`Bearer ${freshToken}`} label="凭证值">
                <code className="profile-token-secret">{`Bearer ${freshToken}`}</code>
              </CopyableLine>
            ) : tokenInfo.hasToken ? (
              <strong>
                {tokenInfo.tokenPrefix}
                {"••••••••"}
                <span className="profile-token-hint">（完整值仅生成时可见，丢失请重新生成）</span>
              </strong>
            ) : (
              <span className="profile-token-hint">请先生成凭证</span>
            )}
          </div>
        </div>

        {!tokenInfo.hasToken && !freshToken && <div className="table-empty">尚未生成个人凭证</div>}

        {(tokenInfo.hasToken || freshToken) && (
          <div className="profile-token-meta">
            {tokenInfo.name && <span>名称：{tokenInfo.name}</span>}
            {tokenInfo.createdAt && <span>创建：{tokenInfo.createdAt.replace("T", " ").slice(0, 19)}</span>}
            {tokenInfo.lastUsedAt && <span>最近使用：{tokenInfo.lastUsedAt.replace("T", " ").slice(0, 19)}</span>}
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-title action-title">
          <div>
            <h2>我的权限</h2>
            <p>由角色汇总而来，如需调整请联系管理员在「用户权限」中配置。</p>
          </div>
        </div>
        {permissionSections.length === 0 ? (
          <div className="table-empty">当前账号未分配任何权限</div>
        ) : (
          <div className="profile-permission-groups">
            {permissionSections.map((section) => (
              <div key={section.title} className="profile-permission-group">
                <h3>{section.title}</h3>
                <ul>
                  {section.items.map((item) => (
                    <li key={item.key}>
                      <strong>{item.label}</strong>
                      <em>{item.key}</em>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
