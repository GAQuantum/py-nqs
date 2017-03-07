import heisenberg1d
import nqs
import sampler
import trainer
import numpy as np

nruns = 1000

wf = nqs.Nqs("./Ground/Heisenberg1d_40_1_1.npz")
np.random.seed(529299)
r = np.random.random(wf.W.shape)
wf.W = wf.W*0 + 0.4*r


h = heisenberg1d.Heisenberg1d(40, 1)
base_array = np.concatenate(
                (np.ones(int(20)), -1 * np.ones(int(20))))  # make an array of half 1, half -1
state = np.random.permutation(base_array)  # return a random permutation of the half 1, half-1 array
wf.init_lt(state)

s = sampler.Sampler(wf, h)
s.run(nruns)

state = s.state
wf.init_lt(state)

def gamma_fun(p):
    return 1e-3

t = trainer.Trainer(h)
wf, elist = t.train(wf,state,1000,101,gamma_fun, file='Outputs/test', out_freq=20)

#h = ising1d.Ising1d(40,1)
s = sampler.Sampler(wf, h)
s.run(nruns)
