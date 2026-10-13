from django.urls import path

from .views import app_data, audit_sensitive_access, auth_login, auth_logout, auth_me, collection_item, collection_items, delete_document, download_document, finance_validation, finance_validation_ignore, generate_service_contract, generate_standalone_service_contract, official_site_inquiry, platform_account_sensitive_value, upload_document, website_leads


urlpatterns = [
    path("auth/login/", auth_login, name="auth-login"),
    path("auth/me/", auth_me, name="auth-me"),
    path("auth/logout/", auth_logout, name="auth-logout"),
    path("audit/sensitive-access/", audit_sensitive_access, name="audit-sensitive-access"),
    path("platform-accounts/<str:record_id>/sensitive/<str:field>/", platform_account_sensitive_value, name="platform-account-sensitive-value"),
    path("validation/finance/", finance_validation, name="finance-validation"),
    path("validation/finance/ignore/", finance_validation_ignore, name="finance-validation-ignore"),
    path("projects/<str:project_id>/generate-contract/", generate_service_contract, name="generate-service-contract"),
    path("contracts/generate/", generate_standalone_service_contract, name="generate-standalone-service-contract"),
    path("documents/upload/", upload_document, name="document-upload"),
    path("documents/<str:file_id>/", download_document, name="document-download"),
    path("documents/<str:file_id>/delete/", delete_document, name="document-delete"),
    path("app-data/", app_data, name="app-data"),
    path("collections/<str:collection>/", collection_items, name="collection-items"),
    path("collections/<str:collection>/<str:record_id>/", collection_item, name="collection-item"),
    path("website-leads/", website_leads, name="website-leads"),
    path("website-leads", website_leads, name="website-leads-no-slash"),
    path("official-site-inquiry/", official_site_inquiry, name="official-site-inquiry"),
    path("official-site-inquiry", official_site_inquiry, name="official-site-inquiry-no-slash"),
]
