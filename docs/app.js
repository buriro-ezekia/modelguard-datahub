const stages = [
  {
    badge: 'regression detected', className: 'failed',
    output: `$ modelguard evaluate\nmetric: f1_score\nbaseline: 0.842\ncandidate: 0.771\nstatus: failed\nexit_code: 1`
  },
  {
    badge: 'context collected', className: 'info',
    output: `$ modelguard context collect --provider fixture\nmodel: churn-model-v3\nschema_fields: 2\nupstream_assets: 3\ndownstream_deployments: 1\nprovider: fixture`
  },
  {
    badge: 'root cause ranked', className: 'ranked',
    output: `$ modelguard diagnose\nH001 feature_transformation  1.0000  high\nH002 source_data_quality    0.6025  medium\nH003 schema_contract        0.2775  low\nevidence_records: 11`
  },
  {
    badge: 'repair proposed', className: 'proposed',
    output: `$ modelguard repair\nstrategy: guarded_division\nchanged_files: 1\nadded_lines: 2\npatch_guard: approved\nsource_workspace_changed: false`
  },
  {
    badge: 'repair validated', className: 'validated',
    output: `$ isolated validation\npython_compile: passed\ntargeted_tests: 3 passed\ninvalid_values: 37 -> 0\nf1_score: 0.771 -> 0.842\nmetric_gate: passed`
  },
  {
    badge: 'outcome published', className: 'published',
    output: `$ modelguard publish --apply\ngithub: created\ndatahub: raised_and_resolved\ndelivery: delivery-43a1891cc0d4\nrepeat github: noop\nrepeat datahub: noop`
  }
];

let currentStage = 0;
let timer = null;
const output = document.getElementById('terminalOutput');
const badge = document.getElementById('terminalBadge');
const step = document.getElementById('terminalStep');
const progress = document.getElementById('terminalProgress');
const stageButtons = [...document.querySelectorAll('.terminal-nav button')];

function showStage(index) {
  currentStage = index;
  const stage = stages[index];
  output.textContent = stage.output;
  badge.textContent = stage.badge;
  badge.className = `status-badge ${stage.className}`;
  step.textContent = `${index + 1} / ${stages.length}`;
  progress.style.width = `${((index + 1) / stages.length) * 100}%`;
  stageButtons.forEach((button, buttonIndex) => button.classList.toggle('active', buttonIndex === index));
}

stageButtons.forEach((button, index) => button.addEventListener('click', () => {
  clearInterval(timer);
  showStage(index);
}));

document.getElementById('replayButton').addEventListener('click', () => {
  clearInterval(timer);
  showStage(0);
  document.querySelector('.terminal-card').scrollIntoView({ behavior: 'smooth', block: 'center' });
  timer = setInterval(() => {
    if (currentStage >= stages.length - 1) {
      clearInterval(timer);
      return;
    }
    showStage(currentStage + 1);
  }, 1250);
});

document.getElementById('copyCommand').addEventListener('click', async (event) => {
  const command = document.getElementById('showcaseCommand').textContent;
  try {
    await navigator.clipboard.writeText(command);
    event.currentTarget.textContent = 'Copied';
    setTimeout(() => { event.currentTarget.textContent = 'Copy'; }, 1400);
  } catch {
    event.currentTarget.textContent = 'Select';
  }
});
