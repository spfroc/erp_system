// form-submit.js — 只调用旧接口 official-site-inquiry（发短信 + 录商机）

var LEGACY_INQUIRY_API = '/api/official-site-inquiry';
var SUCCESS_MESSAGE = '感谢您的咨询！我们的专业顾问会尽快与您联系。';

function resolveLegacyApiUrl(apiUrl) {
    var url = apiUrl == null ? '' : String(apiUrl);
    if (url.charAt(0) === '/' && url.indexOf('official-site-inquiry') !== -1) {
        return url;
    }
    return LEGACY_INQUIRY_API;
}

function buildLegacyPayload(values) {
    return {
        enterprise_name: String(
            values.enterprise_name || values.companyName || values.company || ''
        ).trim(),
        phone: String(values.phone || values.tel || '').trim(),
        name: String(
            values.name || values.contactName || values.contact || ''
        ).trim(),
        platform_name: String(
            values.platform_name || values.platform || ''
        ).trim(),
        requirement: String(
            values.requirement || values.remark || values.message || ''
        ).trim()
    };
}

function submitLegacyInquiry(values, legacyApiUrl) {
    var apiUrl = resolveLegacyApiUrl(legacyApiUrl);
    var payload = buildLegacyPayload(values);

    if (!payload.enterprise_name || !payload.phone) {
        return Promise.resolve({
            ok: false,
            source: 'legacy',
            error: { message: 'missing required fields' }
        });
    }

    return fetch(apiUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
        .then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (data) {
                var ok = data && data.code === 20000;
                return {
                    ok: ok,
                    source: 'legacy',
                    status: response.status,
                    data: data,
                    error: ok ? null : (data && data.message ? data.message : ('HTTP ' + response.status))
                };
            });
        })
        .catch(function (error) {
            console.error('[legacy-inquiry]', error);
            return {
                ok: false,
                source: 'legacy',
                error: error
            };
        });
}

/**
 * 提交咨询：仅旧接口（短信 + 商机）
 */
function submitConsultation(values, options) {
    options = options || {};
    var legacyApiUrl = options.legacyApiUrl;
    var successCallback = options.onSuccess || options.successCallback;
    var errorCallback = options.onError || options.errorCallback;

    var payload = buildLegacyPayload(values);
    if (!payload.enterprise_name || !payload.phone) {
        alert('请填写公司名称和电话。');
        if (errorCallback) errorCallback({ message: 'missing required fields' });
        return Promise.resolve();
    }

    return submitLegacyInquiry(values, legacyApiUrl).then(function (result) {
        if (result.ok) {
            alert(SUCCESS_MESSAGE);
            if (successCallback) successCallback(result);
        } else {
            var msg = result.error || '提交失败，请稍后重试。';
            alert('提交失败: ' + (typeof msg === 'string' ? msg : (msg.message || '请稍后重试')));
            if (errorCallback) errorCallback(result);
        }
        return result;
    });
}

/**
 * @param {string} formSelector
 * @param {string} legacyApiUrl 可省略，默认 /api/official-site-inquiry
 */
function handleFormSubmit(formSelector, legacyApiUrl, successCallback, errorCallback) {
    var form = document.querySelector(formSelector);
    if (!form) {
        console.error('表单未找到：', formSelector);
        return;
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        var values = Object.fromEntries(new FormData(form));
        submitConsultation(values, {
            legacyApiUrl: legacyApiUrl,
            onSuccess: function () {
                form.reset();
                if (successCallback) successCallback.apply(null, arguments);
            },
            onError: errorCallback
        });
    });
}

// 兼容旧页面可能仍调用的方法名
function submitWebsiteLead(values, successCallback, errorCallback) {
    return submitConsultation(values, {
        onSuccess: successCallback,
        onError: errorCallback
    });
}

window.LEGACY_INQUIRY_API = LEGACY_INQUIRY_API;
window.resolveLegacyApiUrl = resolveLegacyApiUrl;
window.buildLegacyPayload = buildLegacyPayload;
window.submitLegacyInquiry = submitLegacyInquiry;
window.submitConsultation = submitConsultation;
window.submitWebsiteLead = submitWebsiteLead;
window.handleFormSubmit = handleFormSubmit;
