<?php
/**
 * Export legacy admin 资料库 + 短信 templates/records from yuncai / center.
 * Usage: php export_library_sms_from_admin.php /path/to/out_dir
 */

function load_env(string $path): array
{
    $cfg = [];
    foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if ($line === '' || str_starts_with($line, '#') || !str_contains($line, '=')) {
            continue;
        }
        [$k, $v] = explode('=', $line, 2);
        $cfg[trim($k)] = trim($v, " \t\"'");
    }
    return $cfg;
}

function pdo_from_env(array $cfg): PDO
{
    $dsn = sprintf(
        'mysql:host=%s;port=%s;dbname=%s;charset=utf8mb4',
        $cfg['DB_HOST'] ?? '127.0.0.1',
        $cfg['DB_PORT'] ?? '3306',
        $cfg['DB_DATABASE'] ?? ''
    );
    return new PDO($dsn, $cfg['DB_USERNAME'] ?? '', $cfg['DB_PASSWORD'] ?? '', [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
}

function table_exists(PDO $pdo, string $table): bool
{
    $stmt = $pdo->prepare('SHOW TABLES LIKE ?');
    $stmt->execute([$table]);
    return (bool) $stmt->fetchColumn();
}

function dump_table(PDO $pdo, string $table): array
{
    if (!table_exists($pdo, $table)) {
        return [];
    }
    return $pdo->query("SELECT * FROM `{$table}`")->fetchAll();
}

$outDir = $argv[1] ?? (getcwd() . '/library_sms_export');
if (!is_dir($outDir) && !mkdir($outDir, 0775, true) && !is_dir($outDir)) {
    fwrite(STDERR, "Cannot create {$outDir}\n");
    exit(1);
}

$adminEnv = load_env('/home/spf/projects/admin/.env');
$centerEnv = load_env('/home/spf/projects/center/.env');
$yuncai = pdo_from_env($adminEnv);
$center = pdo_from_env($centerEnv);

echo "yuncai tables matching customer/note:\n";
foreach ($yuncai->query("SHOW TABLES")->fetchAll(PDO::FETCH_COLUMN) as $t) {
    if (preg_match('/customer|note|sms/i', $t)) {
        $n = $yuncai->query("SELECT COUNT(*) FROM `{$t}`")->fetchColumn();
        echo "  {$t}\t{$n}\n";
    }
}
echo "center tables matching note/sms:\n";
foreach ($center->query("SHOW TABLES")->fetchAll(PDO::FETCH_COLUMN) as $t) {
    if (preg_match('/note|sms|message/i', $t)) {
        $n = $center->query("SELECT COUNT(*) FROM `{$t}`")->fetchColumn();
        echo "  {$t}\t{$n}\n";
    }
}

$customers = dump_table($yuncai, 'customers');
if (!$customers) {
    $customers = dump_table($yuncai, 'customer');
}
$infos = dump_table($yuncai, 'customer_infos');
if (!$infos) {
    $infos = dump_table($yuncai, 'customer_info');
}
$records = dump_table($yuncai, 'customer_touch_records');
$adminCustomers = dump_table($yuncai, 'admin_customers');
$templates = dump_table($yuncai, 'admin_note_templates');
if (!$templates) {
    $templates = dump_table($yuncai, 'admin_note_template');
}

// center SMS records – try common names
$noteCandidates = [];
foreach ($center->query("SHOW TABLES")->fetchAll(PDO::FETCH_COLUMN) as $t) {
    if (preg_match('/note|sms/i', $t)) {
        $noteCandidates[] = $t;
    }
}
$smsTables = [];
foreach ($noteCandidates as $t) {
    $smsTables[$t] = dump_table($center, $t);
}

$payload = [
    'exportedAt' => date('c'),
    'source' => [
        'admin' => $adminEnv['DB_DATABASE'] ?? '',
        'center' => $centerEnv['DB_DATABASE'] ?? '',
        'host' => $adminEnv['DB_HOST'] ?? '',
    ],
    'counts' => [
        'customers' => count($customers),
        'customer_infos' => count($infos),
        'customer_touch_records' => count($records),
        'admin_customers' => count($adminCustomers),
        'admin_note_templates' => count($templates),
    ],
    'customers' => $customers,
    'customer_infos' => $infos,
    'customer_touch_records' => $records,
    'admin_customers' => $adminCustomers,
    'admin_note_templates' => $templates,
    'center_sms_tables' => array_map('count', $smsTables),
    'center_sms' => $smsTables,
];

foreach ($smsTables as $name => $rows) {
    $payload['counts']["center.{$name}"] = count($rows);
}

$rawPath = $outDir . '/library_sms_raw.json';
file_put_contents($rawPath, json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
echo "Wrote {$rawPath}\n";
echo "Counts: " . json_encode($payload['counts'], JSON_UNESCAPED_UNICODE) . "\n";

// Also dump SQL dumps via mysqldump if available
$mysqldump = trim((string) shell_exec('command -v mysqldump'));
if ($mysqldump !== '') {
    $custTables = array_values(array_filter([
        table_exists($yuncai, 'customers') ? 'customers' : null,
        table_exists($yuncai, 'customer_infos') ? 'customer_infos' : (table_exists($yuncai, 'customer_info') ? 'customer_info' : null),
        table_exists($yuncai, 'customer_touch_records') ? 'customer_touch_records' : null,
        table_exists($yuncai, 'admin_customers') ? 'admin_customers' : null,
        table_exists($yuncai, 'admin_note_templates') ? 'admin_note_templates' : (table_exists($yuncai, 'admin_note_template') ? 'admin_note_template' : null),
    ]));
    $runDump = static function (array $env, array $tables, string $outFile) use ($mysqldump): int {
        if (!$tables) {
            return 0;
        }
        $args = [
            $mysqldump,
            '-h' . $env['DB_HOST'],
            '-P' . ($env['DB_PORT'] ?? '3306'),
            '-u' . $env['DB_USERNAME'],
            '-p' . $env['DB_PASSWORD'],
            '--default-character-set=utf8mb4',
            '--single-transaction',
            '--quick',
            $env['DB_DATABASE'],
            ...$tables,
        ];
        $cmd = implode(' ', array_map('escapeshellarg', $args)) . ' > ' . escapeshellarg($outFile);
        passthru($cmd, $code);
        return (int) $code;
    };
    echo 'mysqldump yuncai exit=' . $runDump($adminEnv, $custTables, $outDir . '/yuncai_library.sql') . "\n";
    echo 'mysqldump center exit=' . $runDump($centerEnv, $noteCandidates, $outDir . '/center_sms.sql') . "\n";
}

echo "DONE\n";
