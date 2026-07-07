// Presentational vertical timeline explaining each stage of the analysis pipeline
import React from 'react';
import Icon, { IconName } from './Icon';

interface TimelineStep {
  icon: IconName;
  title: string;
  description: string;
  variant?: 'checkpoint' | 'final';
  tag?: string;
}

const STEPS: TimelineStep[] = [
  {
    icon: 'file-text',
    title: 'Document Extraction',
    description: 'Parses the uploaded PDF with PyMuPDF and pdfplumber to pull out text and tables.',
  },
  {
    icon: 'alert-triangle',
    title: 'Human Review Checkpoint',
    description: 'The pipeline pauses so you can review the extracted content before analysis begins.',
    variant: 'checkpoint',
  },
  {
    icon: 'dollar-sign',
    title: 'Finance Analysis + Compliance',
    description: 'Two agents run at the same time: one analyzes financial metrics, the other checks regulatory compliance.',
    tag: 'Parallel',
  },
  {
    icon: 'bar-chart',
    title: 'Risk Assessment',
    description: 'Evaluates risk factors using the finance and compliance findings.',
  },
  {
    icon: 'file-text',
    title: 'Report Generation',
    description: 'Compiles all findings into a structured draft report.',
  },
  {
    icon: 'alert-triangle',
    title: 'Final Approval Checkpoint',
    description: 'The pipeline pauses again so you can edit and approve the draft before it is finalized.',
    variant: 'checkpoint',
  },
  {
    icon: 'check-circle',
    title: 'Complete',
    description: 'The final PDF report is ready to download.',
    variant: 'final',
  },
];

const WorkflowGuide: React.FC = () => (
  <ol className="workflow-timeline">
    {STEPS.map((step, idx) => (
      <li key={step.title} className={`workflow-timeline-item ${step.variant ? `is-${step.variant}` : ''}`}>
        <div className="workflow-timeline-node">
          <div className="workflow-timeline-icon">
            <Icon name={step.icon} size={14} />
          </div>
          {idx < STEPS.length - 1 && <div className="workflow-timeline-connector" />}
        </div>
        <div className="workflow-timeline-body">
          <div className="workflow-timeline-title">
            <span>{step.title}</span>
            {step.tag && <span className="workflow-timeline-tag">{step.tag}</span>}
          </div>
          <p className="workflow-timeline-desc">{step.description}</p>
        </div>
      </li>
    ))}
  </ol>
);

export default WorkflowGuide;
