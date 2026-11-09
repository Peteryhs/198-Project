import numpy as np
from error_evidence import evidence

def main():
    train=np.array([[1,1,1,.8],[1.1,1.1,1.1,.9],[.9,.9,.9,.7]])
    out=evidence(np.array([.5,.2,.2,.8]),train)
    assert out['error_category']=='not enough evidence to say'
    assert out['deviation_flags']['cycle_duration_s'] and out['deviation_flags']['upper_envelope_g']
    other=evidence(np.array([4,8,9,-.9]),train)
    assert out['training_reference_median']==other['training_reference_median']
    assert out['training_reference_scale']==other['training_reference_scale']
    print('held-out values cannot change references; multi-deviation evidence preserves explicit mechanism refusal')
if __name__=='__main__':main()
