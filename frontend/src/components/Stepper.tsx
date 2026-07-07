// Horizontal workflow stepper showing progress through the analysis pipeline
import React from 'react';
import Icon, { IconName } from './Icon';

export interface Step {
  key: string;
  label: string;
  icon: IconName;
}

interface Props {
  steps: Step[];
  activeIndex: number;
}

const Stepper: React.FC<Props> = ({ steps, activeIndex }) => {
  return (
    <div className="stepper">
      {steps.map((step, idx) => {
        const state = idx < activeIndex ? 'completed' : idx === activeIndex ? 'active' : 'pending';
        return (
          <React.Fragment key={step.key}>
            <div className={`step step-${state}`}>
              <div className="step-circle">
                <Icon name={state === 'completed' ? 'check' : step.icon} size={15} />
              </div>
              <div className="step-label">{step.label}</div>
            </div>
            {idx < steps.length - 1 && (
              <div className={`step-connector ${idx < activeIndex ? 'filled' : ''}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

export default Stepper;
