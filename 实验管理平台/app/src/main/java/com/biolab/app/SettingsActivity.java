package com.biolab.app;

import android.content.SharedPreferences;
import android.os.Bundle;
import android.text.TextUtils;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

public class SettingsActivity extends AppCompatActivity {

    private EditText etServerUrl;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        prefs = getSharedPreferences("biolab", MODE_PRIVATE);
        etServerUrl = findViewById(R.id.et_server_url);
        Button btnSave = findViewById(R.id.btn_save);
        Button btnReset = findViewById(R.id.btn_reset);

        // 加载当前地址
        String currentUrl = prefs.getString("server_url", "http://144.48.240.125:8000");
        etServerUrl.setText(currentUrl);

        btnSave.setOnClickListener(v -> {
            String url = etServerUrl.getText().toString().trim();
            if (TextUtils.isEmpty(url)) {
                Toast.makeText(this, "请输入服务器地址", Toast.LENGTH_SHORT).show();
                return;
            }
            if (!url.startsWith("http://") && !url.startsWith("https://")) {
                url = "http://" + url;
            }
            prefs.edit().putString("server_url", url).apply();
            Toast.makeText(this, "已保存，重启应用生效", Toast.LENGTH_SHORT).show();
            finish();
        });

        btnReset.setOnClickListener(v -> {
            etServerUrl.setText("http://144.48.240.125:8000");
            Toast.makeText(this, "已重置为默认地址", Toast.LENGTH_SHORT).show();
        });
    }
}
