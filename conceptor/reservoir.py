"""
Created on May 25, 2015

@author: littleowen
@note: Implementation fo reservoir network
"""

import numpy as np
import scipy as sp
import numpy.matlib
import conceptor.util as util
import conceptor.logic as logic

class Reservoir:
  """
  An implementaion of reservoir network
  
  """
  
  def __init__(self,
               size_in,
               size_net,
               sr = 1.5,
               in_scale = 1.5,
               bias_scale = 0.2,
               varrho_out = 0.01,
               varrho_w = 0.0001):
    
    """
    Initialize conceptor network
    
    @param size_in: number of input neurons
    @param size_net: number of internal neurons  
    @param sr: spectral radius
    @param in_scale: scaling of input weights
    @param bias_scale: scaling of bias 
    @param washout_length: length of wash-out iteration
    @param learn_length: length of learning iteration
    @param signal_plot_length: length of plot length
    @param varrho_out: Tychonov regularization parameter for W_out
    @param varrho_w: Tychonov regularization parameter for W
    """
    
    # document parameters
    self.size_in = size_in
    self.size_net = size_net
    self.num_pattern = 0
    self.sr = sr
    self.in_scale = in_scale
    self.bias_scale = bias_scale
    self.varrho_out = varrho_out
    self.varrho_w = varrho_w
    
    # initialize weights and parameters
    self.W_star, self.W_in, self.W_bias = util.init_weights(size_in,
                                                      size_net,
                                                      sr,
                                                      in_scale,
                                                      bias_scale)
    self.W_out = np.asarray([])
    self.W = np.asarray([])
    
    self.x_collectors = []
    self.pattern_Rs = []
    self.UR_collectors = []
    self.SR_collectors = []
    self.pattern_collectors = []
    
    self.all_train_args = np.asarray([])
    self.all_train_old_args = np.asarray([])
    self.all_train_outs = np.asarray([])
    
    self.Cs = [] 
    self.Cs.append([]) 
    self.Cs.append([]) 
    self.Cs.append([]) 
    self.Cs.append([])
    
  def clean_storage(self):
    self.W_out = np.asarray([])
    self.W = np.asarray([])
    
    self.x_collectors = []
    self.pattern_Rs = []
    self.UR_collectors = []
    self.SR_collectors = []
    self.pattern_collectors = []
    
    self.all_train_args = np.asarray([])
    self.all_train_old_args = np.asarray([])
    self.all_train_outs = np.asarray([])
    
    self.Cs = [] 
    self.Cs.append([]) 
    self.Cs.append([]) 
    self.Cs.append([]) 
    self.Cs.append([])
    
  def augment(self,
              data):
    """
    Augment the dimension of the original data in reservoir   
    
    @param data: original data to be augmented
    """
    datalen = data.shape[1]
    x = np.random.randn(self.size_net, 1)
    xs = np.tile(x, (1, datalen))
    bias = np.tile(self.W_bias, (1, datalen))
    resultvec = np.zeros((self.size_net, datalen, data.shape[2]))
    for i in range(data.shape[2]):
      us = data[:, : , i]
      xs = np.tanh(self.W_star.dot(xs) + self.W_in.dot(us) + bias)
      resultvec[:, :, i] = xs
      return resultvec.swapaxes(1,2).reshape(-1, datalen, order = 'F'), resultvec
      
    
    
  def drive_reservoir(self,
                      pattern,
                      washout_length):
    """
    harvest data from network externally driven by one pattern   
    
    @param pattern: input pattern as a numpy arrays
    """
    learn_length = pattern.shape[1] - washout_length
    x_collector = np.zeros((self.size_net, learn_length))
    x_old_collector = np.zeros((self.size_net, learn_length))
    p_collector = np.zeros((self.size_in, learn_length))
    x = np.zeros((self.size_net, 1))
    
    for n in range(washout_length + learn_length):
      u = pattern[:,n][None].T
      x_old = x
      x = np.tanh(self.W_star.dot(x) + self.W_in.dot(u) + self.W_bias)
      if n > washout_length - 1:
        x_collector[:, n - washout_length] = x[:,0]
        x_old_collector[:, n - washout_length] = x_old[:,0]
        p_collector[:, n - washout_length] = u[:,0];

    self.x_collectors.append(x_collector)
    
    # store correlation matrix and its eigen vectors and eigen values 
    R = x_collector.dot(x_collector.T) / learn_length
    Ux, Sx, _ = np.linalg.svd(R)
    self.SR_collectors.append(Sx)
    self.UR_collectors.append(Ux)
    self.pattern_Rs.append(R)

    
    self.pattern_collectors.append(p_collector)
    
    # store training data
    if not self.all_train_args.size:
      self.all_train_args = x_collector
    else:
      self.all_train_args = np.hstack((self.all_train_args, x_collector))
      
    if not self.all_train_old_args.size:
      self.all_train_old_args = x_old_collector
    else:
      self.all_train_old_args = np.hstack((self.all_train_old_args, x_old_collector))
      
    if not self.all_train_outs.size:
      self.all_train_outs = p_collector
    else:
      self.all_train_outs = np.hstack((self.all_train_outs, p_collector))

    self.num_pattern += 1
    
    
  def compute_projector(self,
                        R,
                        alpha = 10):  
    """
    Compute projector (conceptor matrix)
    
    @param R: network state correlation matrix
    @param alpha: aperture 
    """
    
    U, S, _ = np.linalg.svd(R)
    S_new = (np.diag(S).dot(np.linalg.inv(np.diag(S) + alpha ** (-2) * np.eye(self.size_net))))
        
    C = U.dot(S_new).dot(U.T)
    
    self.Cs[0].append(C)
    self.Cs[1].append(U)
    self.Cs[2].append(np.diag(S_new))
    self.Cs[3].append(S)
    
  def compute_projectors(self,
                         alphas):  
    """
    Compute projectors (conceptor matrices)
    
    @param R: network state correlation matrix
    @param alpha: aperture 
    """
    
    if self.Cs:
      self.Cs = [] 
      self.Cs.append([]) 
      self.Cs.append([]) 
      self.Cs.append([]) 
      self.Cs.append([])

    for p in range(self.num_pattern):
      R = self.pattern_Rs[p]
      alpha = alphas[p]
      self.compute_projector(R)

    
  def compute_W_out(self,
                    varrho_out = None):
    """
    Compute output weights so that the output equals input pattern
    
    @param varrho_out: Tychonov regularization parameter
    """
    if varrho_out is None:
        varrho_out = self.varrho_out
    self.W_out = np.linalg.inv(self.all_train_args.dot(self.all_train_args.T) + varrho_out * np.eye(self.size_net)).dot(self.all_train_args).dot(self.all_train_outs.T).T
    
    
  def compute_W(self,
                varrho_w = None):
    """
    Compute reserior weights 
    
    @param varrho_w: Tychonov regularization parameter
    """
    if varrho_w is None:
        varrho_w = self.varrho_w
    total_length = self.all_train_args.shape[1]
    W_targets = np.arctanh(self.all_train_args) - np.matlib.repmat(self.W_bias, 1, total_length)
    self.W = np.linalg.inv(self.all_train_old_args.dot(self.all_train_old_args.T) + varrho_w * np.eye(self.size_net)).dot(self.all_train_old_args).dot(W_targets.T).T;
    
    
  def train(self, 
            patterns,
            washout_length):
    """
    Training procedure for conceptor network
    
    @param patterns: a list of numpy arrays as patterns
    """
    for i in range(len(patterns)):
      self.drive_reservoir(patterns[i], washout_length)
    
    self.compute_W_out(self.varrho_out)
    self.compute_W(self.varrho_w)
    
    
  def recognition_train(self, datalist, apN = 9, out_mode = "simple"):
    """
    Training procedure for dynamic recogniton
    
    @param datalist
    """
    R_list = []
    C_prem_list = []
    apsExploreExponents = np.asarray(range(apN))
    apt_list = []
    C_list = []
    intPts = np.arange(apsExploreExponents[0], apsExploreExponents[-1] + 0.01, 0.01)
    for data in datalist:
      R = (data.dot(data.T)) / data.shape[1]
      R_list.append(R)
      I = np.eye(R.shape[0])
      C_prem = R.dot(np.linalg.inv(R + I))
      C_prem_list.append(C_prem)
      Cnorm_list = []
      for i in range(apN):
        C_temp = logic.PHI(C_prem, 2 ** apsExploreExponents[i])
        Cnorm_list.append(np.linalg.norm(C_temp ,'fro') ** 2)
      norms = np.asarray(Cnorm_list)
      interpfun = sp.interpolate.interp1d(apsExploreExponents, norms, kind = 'cubic')
      norms_Intpl = interpfun(intPts)
      norms_Intpl_Grad = (norms_Intpl[1:] - norms_Intpl[0:-1]) / 0.01
      aptind = np.argmax(abs(norms_Intpl_Grad), axis = 0)
      apt = 2 ** intPts[aptind]
      apt_list.append(apt)
    apt = np.mean(apt_list)
    for C_prem in C_prem_list:
      C_list.append(logic.PHI(C_prem, apt))
    if out_mode == "complete":
      return C_list, R_list, C_prem_list, apt_list
    else:
      return C_list


  def recognition_predict(self, testdata, C_list):
    evidence_list = []
    for C in C_list:
      evidence = sum(testdata * (C.dot(testdata)))
      evidence_list.append(evidence)
    evidence = np.row_stack(evidence_list)
    return np.argmax(evidence, axis = 0), evidence
    