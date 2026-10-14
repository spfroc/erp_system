<?php
/**
 * Stream-export customers + SMS to ndjson/sql under out dir.
 * php -d memory_limit=256M export_library_sms_stream.php /path/out
 */

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

function pdo_env(array $cfg): PDO
{
    $pdo = new PDO(
        sprintf('mysql:host=%s;port=%s;dbname=%s;charset=utf8mb4', $cfg['DB_HOST'], $cfg['DB_PORT'] ?? '3306', $cfg['DB_DATABASE']),
        $cfg['DB_USERNAME'],
        $cfg['DB_PASSWORD'],
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]
    );
    $pdo->setAttribute(PDO::MYSQL_ATTR_USE_BUFFERED_QUERY, false);
    return $pdo;
}

function stream_table(PDO $pdo, string $sql, string $outFile): int
{
    $fh = fopen($outFile, 'wb');
    if (!$fh) {
        throw new RuntimeException("Cannot write {$outFile}");
    }
    $stmt = $pdo->query($sql);
    $n = 0;
    while ($row = $stmt->fetch()) {
        fwrite($fh, json_encode($row, JSON_UNESCAPED_UNICODE) . "\n");
        $n++;
        if ($n % 5000 === 0) {
            echo "  {$outFile}: {$n}\n";
        }
    }
    fclose($fh);
    return $n;
}

function mysqldump_tables(array $env, array $tables, string $outFile): int
{
    if (!$tables) return 0;
    $bin = trim((string) shell_exec('command -v mysqldump'));
    if ($bin === '') {
        echo "mysqldump not found, skip {$outFile}\n";
        return 1;
    }
    $args = [
        $bin,
        '-h' . $env['DB_HOST'],
        '-P' . ($env['DB_PORT'] ?? '3306'),
        '-u' . $env['DB_USERNAME'],
        '-p' . $env['DB_PASSWORD'],
        '--default-character-set=utf8mb4',
        '--single-transaction',
        '--quick',
        '--skip-lock-tables',
        $env['DB_DATABASE'],
        ...$tables,
    ];
    $cmd = implode(' ', array_map('escapeshellarg', $args)) . ' > ' . escapeshellarg($outFile);
    passthru($cmd, $code);
    return (int) $code;
}

$outDir = $argv[1] ?? '/tmp/library_sms_export';
if (!is_dir($outDir) && !mkdir($outDir, 0775, true) && !is_dir($outDir)) {
    fwrite(STDERR, "Cannot create {$outDir}\n");
    exit(1);
}

$adminEnv = load_env('/home/spf/projects/admin/.env');
$centerEnv = load_env('/home/spf/projects/center/.env');
$yuncai = pdo_env($adminEnv);
$center = pdo_env($centerEnv);

$meta = [
    'exportedAt' => date('c'),
    'host' => gethostname(),
    'source' => [
        'adminDb' => $adminEnv['DB_DATABASE'],
        'centerDb' => $centerEnv['DB_DATABASE'],
        'dbHost' => $adminEnv['DB_HOST'],
    ],
    'counts' => [],
];

echo "Dumping SQL...\n";
$meta['mysqldump'] = [
    'yuncai' => mysqldump_tables(
        $adminEnv,
        ['customers', 'customer_touch_records', 'admin_customers', 'admin_note_templates', 'customer_contracts'],
        $outDir . '/yuncai_library.sql'
    ),
    'center' => mysqldump_tables(
        $centerEnv,
        ['short_messages', 'failed_short_message_mobiles'],
        $outDir . '/center_sms.sql'
    ),
];

echo "Streaming ndjson...\n";
$meta['counts']['customers'] = stream_table($yuncai, 'SELECT * FROM customers ORDER BY id', $outDir . '/customers.ndjson');
$meta['counts']['customer_touch_records'] = stream_table($yuncai, 'SELECT * FROM customer_touch_records ORDER BY id', $outDir . '/customer_touch_records.ndjson');
$meta['counts']['admin_customers'] = stream_table($yuncai, 'SELECT * FROM admin_customers ORDER BY id', $outDir . '/admin_customers.ndjson');
$meta['counts']['admin_note_templates'] = stream_table($yuncai, 'SELECT * FROM admin_note_templates ORDER BY id', $outDir . '/admin_note_templates.ndjson');
$meta['counts']['short_messages'] = stream_table($center, 'SELECT * FROM short_messages ORDER BY id', $outDir . '/short_messages.ndjson');
$meta['counts']['failed_short_message_mobiles'] = stream_table($center, 'SELECT * FROM failed_short_message_mobiles ORDER BY id', $outDir . '/failed_short_message_mobiles.ndjson');

file_put_contents($outDir . '/manifest.json', json_encode($meta, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
echo "Manifest:\n" . json_encode($meta, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n";
echo "DONE {$outDir}\n";
