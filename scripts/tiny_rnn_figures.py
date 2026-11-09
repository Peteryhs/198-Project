"""Render the saved matched-cohort comparison; no fitting or model selection."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    root=Path('docs/runs/phase6-rnn')
    reports=[json.loads((root/f'results-{side}.json').read_text()) for side in 'LR']
    assert [r['retained_series'] for r in reports]==[301,306]
    fig,axes=plt.subplots(1,2,figsize=(10,5),layout='constrained')
    for ax,task,title in zip(axes,['quality','exercise'],['Whole-recording quality','Exercise identity']):
        x=np.arange(2)
        for delta,key,label,color in [(-.19,'accepted_baseline_agreement','Current classifier','#8c8279'),(.19,'rnn_agreement','Tiny GRU','#9a3b12')]:
            values=[100*r['metrics'][task][key] for r in reports]
            bars=ax.bar(x+delta,values,width=.36,label=label,color=color)
            ax.bar_label(bars,labels=[f'{v:.1f}%' for v in values],padding=3)
        ax.set(ylim=(0,106),xticks=x,xticklabels=['Left pair','Right pair'],ylabel='Whole-series agreement (%)',title=title)
        ax.spines[['right','top']].set_visible(False)
    axes[0].legend(loc='lower left')
    fig.suptitle('One tiny GRU learned, but did not improve on the current classifier\nSame real recordings and cycles; 30-volunteer held-out testing; 301 / 306 retained series',fontsize=13)
    out=Path('docs/figures/phase6-rnn');out.mkdir(parents=True,exist_ok=True)
    fig.savefig(out/'model-comparison.png',dpi=150,bbox_inches='tight')
    svg=out/'model-comparison.svg';fig.savefig(svg,bbox_inches='tight')
    svg.write_text('\n'.join(s.rstrip() for s in svg.read_text().splitlines())+'\n')
    plt.close(fig)
    print('Saved matched-cohort GRU/baseline chart; source values are unchanged saved results')


if __name__=='__main__':main()
