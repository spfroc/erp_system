<?php
function load_env(string $path): array
{
    $cfg = [];
    foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if ($line === '' || str_starts_with($line, '#') || !str_contains($line, '=')) continue;
        [$k, $v] = explode('=', $line, 2);
        $cfg[trim($k)] = trim($v, " \t\"'");
    }
    return $cfg;
}

$admin = load_env('/home/spf/projects/admin/.env');
$center = load_env('/home/spf/projects/center/.env');
$y = new PDO(
    sprintf('mysql:host=%s;port=%s;dbname=%s;charset=utf8mb4', $admin['DB_HOST'], $admin['DB_PORT'] ?? '3306', $admin['DB_DATABASE']),
    $admin['DB_USERNAME'],
    $admin['DB_PASSWORD'],
    [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]
);
$c = new PDO(
    sprintf('mysql:host=%s;port=%s;dbname=%s;charset=utf8mb4', $center['DB_HOST'], $center['DB_PORT'] ?? '3306', $center['DB_DATABASE']),
    $center['DB_USERNAME'],
    $center['DB_PASSWORD'],
    [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]
);

echo "CUSTOMERS COLUMNS\n";
foreach ($y->query('DESCRIBE customers') as $r) {
    echo $r['Field'] . "\t" . $r['Type'] . "\n";
}
echo "SAMPLE CUSTOMER\n";
echo json_encode($y->query('SELECT * FROM customers ORDER BY id DESC LIMIT 1')->fetch(), JSON_UNESCAPED_UNICODE) . "\n";
echo "ADMIN_NOTE_TEMPLATES\n";
foreach ($y->query('DESCRIBE admin_note_templates') as $r) {
    echo $r['Field'] . "\t" . $r['Type'] . "\n";
}
echo "SAMPLE TEMPLATE\n";
echo json_encode($y->query('SELECT * FROM admin_note_templates LIMIT 1')->fetch(), JSON_UNESCAPED_UNICODE) . "\n";
echo "SHORT_MESSAGES COLUMNS\n";
foreach ($c->query('DESCRIBE short_messages') as $r) {
    echo $r['Field'] . "\t" . $r['Type'] . "\n";
}
echo "SAMPLE SHORT_MESSAGE\n";
echo json_encode($c->query('SELECT * FROM short_messages ORDER BY id DESC LIMIT 1')->fetch(), JSON_UNESCAPED_UNICODE) . "\n";
echo "FAILED_SHORT_MESSAGE_MOBILES COLUMNS\n";
foreach ($c->query('DESCRIBE failed_short_message_mobiles') as $r) {
    echo $r['Field'] . "\t" . $r['Type'] . "\n";
}
