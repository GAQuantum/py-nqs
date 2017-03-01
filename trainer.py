import numpy as np
from scipy.sparse.linalg import cg
import sampler


class Trainer:
    def __init__(self, h, reg_list=(100, 0.9, 1e-4)):
        self.h = h  # Hamiltonian to evaluate wf against
        self.nspins = h.nspins
        self.reg_list = reg_list  # Parameters for regularization
        self.step_count = 0

    def train(self, wf, init_state, batch_size, num_steps, gamma,printfreq = 25,file = '', out_freq = 0):
        state = init_state
        elist = np.zeros(num_steps, dtype=complex) #list of energies to evaluate
        for step in range(num_steps):
            # First call the update_vector function to get our set of updates and the new state (so process thermalizes)
            updates, state, elist[step] = self.update_vector(wf, state, batch_size, gamma)
            # Now apply appropriate parts of the update vector to wavefunction parameters
            wf.a += updates[0:wf.nv]
            wf.b += updates[wf.nv:wf.nh + wf.nv]
            wf.W += np.reshape(updates[wf.nv + wf.nh:], wf.W.shape)

            if step % printfreq == 0:
                print("Completed training step {}".format(step))
                print("Current energy per spin: {}".format(elist[step]))

            if out_freq > 0 and step % out_freq == 0:
                wf.save_parameters(file+str(step))

        return wf, elist

    def update_vector(self, wf, init_state, batch_size, gamma, therm=False):  # Get the vector of updates
        samp = sampler.Sampler(wf, self.h)  # start a sampler
        samp.nflips = self.h.minflips
        samp.state = np.copy(init_state)
        samp.reset_av()
        if therm == True:
            samp.thermalize(batch_size)
        elocals = np.zeros(batch_size, dtype=complex)  # Elocal results at each sample
        deriv_vectors = np.zeros((batch_size, wf.nh + wf.nv + wf.nh * wf.nv), dtype=complex)
        states = []

        for sample in range(batch_size):
            samp.move()
            states.append(samp.state)
            elocals[sample] = self.get_elocal(samp.state, samp.wf)
            deriv_vectors[sample] = self.get_deriv_vector(samp.state, samp.wf)

        # Now that we have all the data from sampling let's run our statistics
        cov = self.get_covariance(deriv_vectors)
        forces = self.get_forces(elocals, deriv_vectors)

        # Now we calculate the updates as
        #updates = -gamma * np.dot(np.linalg.pinv(cov), forces)
        vec, info = cg(cov, forces)
        updates = -gamma*vec
        self.step_count += batch_size
        return updates, samp.state, np.mean(elocals)/self.nspins

    def get_elocal(self, state, wf):  # Function to calculate local energies; see equation A2 in Carleo and Troyer
        eloc = 0j  # Start with 0
        mel, flips = self.h.find_conn(state)  # Get all S' that connect to S via H and their matrix elems
        for flip in range(len(flips)):
            eloc += mel[flip] * wf.pop(state, flips[flip])

        return eloc

    def get_deriv_vector(self, state, wf):
        # The derivative vector is a vector which contains the following elements in one column:
        # First: derivative of psi(S) w.r.t. visible unit biases (wf.Nv of them)
        # Second: the hidden unit biases (wf.Nh of them)
        # Third: The weights (wf.Nh * wf.Nv)
        # See Carleo C3-5 for formulas

        vector = np.zeros(wf.nv + wf.nh + wf.nv * wf.nh, dtype=complex)  # initialize

        for bias in range(wf.nv):  # visible unit biases
            vector[bias] = state[bias]

        for bias in range(wf.nh):  # hidden unit biases
            vector[wf.nv + bias] = np.tanh(wf.Lt[bias])

        for v in range(wf.nv):
            for h in range(wf.nh):
                vector[wf.nh + wf.nv + wf.nh * v + h] = state[v] * np.tanh(wf.Lt[h])

        return vector

    def get_covariance(self, deriv_vectors):
        # I'm writing this rather than using np.cov because I am not sure numpy handles complex values right

        omean = np.mean(deriv_vectors, axis=0)  # First get the mean O vector
        outers = np.zeros((deriv_vectors.shape[1],deriv_vectors.shape[1]), dtype=complex)# empty list of outer product matrices
        outer_shape = np.empty([deriv_vectors.shape[1], deriv_vectors.shape[1]],dtype=complex)
        omean_outer_shape = np.empty([omean.shape[0], omean.shape[0]], dtype=complex)
        for vec in deriv_vectors:
            outers += np.outer(np.conj(vec), vec, outer_shape) # First term in A4
        mean_outer = outers/deriv_vectors.shape[0]  # Get the mean outer product matrix
        smat = mean_outer - np.outer(np.conj(omean), omean, omean_outer_shape)  # Eq A4
        # smat += max(self.reg_list[0]*self.reg_list[1]**self.step_count, self.reg_list[2]) * np.diag(np.diag(smat))
        return smat

    def get_forces(self, elocals, deriv_vectors):
        emean = np.mean(elocals)  # mean local energy
        omean = np.mean(deriv_vectors, axis=0)  # mean derivative vector
        correlator = np.mean([i[0] * np.conj(i[1]) for i in zip(elocals, deriv_vectors)], axis=0)
        # pair the local energies with Ovecs and then calculate mean

        return correlator - emean * np.conj(omean)

