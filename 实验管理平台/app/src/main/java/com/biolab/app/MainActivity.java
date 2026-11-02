package com.biolab.app;

import android.annotation.SuppressLint;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.util.Base64;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private ProgressBar progressBar;
    private SharedPreferences prefs;
    private String serverUrl;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences("biolab", MODE_PRIVATE);
        serverUrl = prefs.getString("server_url", "http://144.48.240.125:8000");

        webView = findViewById(R.id.webview);
        progressBar = findViewById(R.id.progressBar);

        initWebView();
        loadUrl(serverUrl);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void initWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setSupportZoom(true);

        // 混合内容（HTTP/HTTPS）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        }

        // Cookie 支持
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, true);

        // 供网页保存导出文件（WebView 自身无法保存 blob 下载）
        webView.addJavascriptInterface(new DownloadBridge(), "AndroidDownload");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                // 导出/下载模板：在页面内走带鉴权的下载，不再跳出应用到外部浏览器
                if (url.contains("/api/")
                        && (url.contains("/export") || url.contains("/template") || url.contains("/download"))) {
                    view.evaluateJavascript("downloadFile('" + url + "')", null);
                    return true;
                }
                view.loadUrl(url);
                return true;
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                super.onPageStarted(view, url, favicon);
                progressBar.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                progressBar.setVisibility(View.GONE);
            }

            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                super.onReceivedError(view, errorCode, description, failingUrl);
                if (errorCode == WebViewClient.ERROR_CONNECT || errorCode == WebViewClient.ERROR_TIMEOUT) {
                    showNetworkError();
                }
            }

            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                // 开发环境允许 SSL 错误（生产环境应移除）
                handler.proceed();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                super.onProgressChanged(view, newProgress);
                progressBar.setProgress(newProgress);
            }
        });

        // 长按菜单（复制等）
        registerForContextMenu(webView);
    }

    /**
     * 网页下载桥：接收文件 base64，保存到应用下载目录并调起系统打开
     * 由 /static/js/api.js 的 downloadFile() 调用
     */
    public class DownloadBridge {
        @JavascriptInterface
        public void saveFile(String filename, String mimeType, String base64) {
            try {
                String name = (filename == null || filename.isEmpty()) ? "download" : filename;
                name = name.replaceAll("[\\\\/:*?\"<>|]", "_");
                byte[] bytes = Base64.decode(base64, Base64.DEFAULT);
                File dir = getExternalFilesDir("downloads");
                if (dir == null) dir = new File(getFilesDir(), "downloads");
                if (!dir.exists() && !dir.mkdirs()) throw new IOException("无法创建下载目录");
                File file = new File(dir, name);
                try (FileOutputStream out = new FileOutputStream(file)) {
                    out.write(bytes);
                }
                final File saved = file;
                final String mime = (mimeType == null || mimeType.isEmpty())
                        ? "application/octet-stream" : mimeType;
                runOnUiThread(() -> openFile(saved, mime));
            } catch (Exception e) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this,
                        "保存失败：" + e.getMessage(), Toast.LENGTH_LONG).show());
            }
        }
    }

    private void openFile(File file, String mimeType) {
        try {
            Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".fileprovider", file);
            Intent intent = new Intent(Intent.ACTION_VIEW)
                    .setDataAndType(uri, mimeType)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            Toast.makeText(this, "已保存：" + file.getName(), Toast.LENGTH_SHORT).show();
            startActivity(Intent.createChooser(intent, "打开文件"));
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "文件已保存：" + file.getAbsolutePath()
                    + "\n请安装 WPS 或 Excel 后打开", Toast.LENGTH_LONG).show();
        }
    }

    private void loadUrl(String url) {
        webView.loadUrl(url);
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        // 双击返回键退出
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            showExitDialog();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    private void showExitDialog() {
        new AlertDialog.Builder(this)
                .setTitle("退出应用")
                .setMessage("确定要退出实验管理平台吗？")
                .setPositiveButton("退出", (dialog, which) -> finish())
                .setNegativeButton("取消", null)
                .show();
    }

    private void showNetworkError() {
        new AlertDialog.Builder(this)
                .setTitle("网络连接失败")
                .setMessage("无法连接到服务器，请检查网络设置或修改服务器地址。")
                .setPositiveButton("设置", (dialog, which) -> {
                    Intent intent = new Intent(MainActivity.this, SettingsActivity.class);
                    startActivity(intent);
                })
                .setNegativeButton("重试", (dialog, which) -> loadUrl(serverUrl))
                .show();
    }

    @Override
    protected void onResume() {
        super.onResume();
        webView.onResume();
    }

    @Override
    protected void onPause() {
        super.onPause();
        webView.onPause();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}
