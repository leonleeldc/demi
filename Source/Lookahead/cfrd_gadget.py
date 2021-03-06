'''''
--- Uses the the CFR-D gadget to generate opponent ranges for re-solving.
--
-- See [Solving Imperfect Information Games Using Decomposition](http://poker.cs.ualberta.ca/publications/aaai2014-cfrd.pdf)
-- @classmod cfrd_gadget
'''''
import sys
import os
import numpy as np
import torch
sys.path.insert(0, '../Settings')
sys.path.insert(0, '../Game')
sys.path.insert(0, '../..')
print('path = ', os.path.abspath('../..'))

import arguments
import constants
import game_settings
import tools


class CFRDGadget():
    # arguments = require 'Settings.arguments'
    # constants = require 'Settings.constants'
    # game_settings = require 'Settings.game_settings'
    # tools = require 'tools'
    # card_tools = require 'Game.card_tools'

    '''
    --- Constructor
    -- @param board board card
    -- @param player_range an initial range vector for the opponent
    -- @param opponent_cfvs the opponent counterfactual values vector used for re-solving
    '''

    def __init(self, board, player_range, opponent_cfvs):
        assert (board)
        self.input_opponent_range = player_range.clone()
        self.input_opponent_value = opponent_cfvs.clone()
        self.curent_opponent_values = arguments.Tensor(game_settings.card_count)
        self.regret_epsilon = 1.0 / 100000000

        ##--2 stands for 2 actions: play/terminate
        #self.opponent_reconstruction_regret = arguments.params['Tensor'](2, game_settings.card_count)
        self.opponent_reconstruction_regret = np.zeros(np.shape([2,game_settings.card_count]))
        self.play_current_strategy = np.zeros(game_settings.card_count)
        self.terminate_current_strategy = np.zeros(game_settings.card_count)
        self.terminate_regrets = np.zeros(game_settings.card_count)
        self.total_values = np.zeros(game_settings.card_count)
        self.play_regrets = np.zeros(game_settings.card_count)
        self.range_mask = np.zeros(game_settings.card_count)
        #self.play_current_strategy = arguments.Tensor(game_settings.card_count):fill(0)
        #self.terminate_current_strategy = arguments.Tensor(game_settings.card_count):fill(1)
        ##--holds achieved CFVs at each iteration so that we can compute regret
        #self.total_values = arguments.Tensor(game_settings.card_count)
        #self.terminate_regrets = arguments.Tensor(game_settings.card_count):fill(0)
        #self.play_regrets = arguments.Tensor(game_settings.card_count):fill(0)
        ##--init range mask for masking out impossible hands
        ## self.range_mask = card_tools.get_possible_hand_indexes(board)
    '''
    --- Uses one iteration of the gadget game to generate an opponent range for
    -- the current re-solving iteration.
    -- @param current_opponent_cfvs the vector of cfvs that the opponent receives
    -- with the current strategy in the re-solve game
    -- @param iteration the current iteration number of re-solving
    -- @return the opponent range vector for this iteration
    '''

    def compute_opponent_range(self, current_opponent_cfvs, iteration):
        play_values = current_opponent_cfvs
        terminate_values = self.input_opponent_value

        ##--1.0 compute current regrets
        torch.mul(self.total_values, play_values, self.play_current_strategy)
        self.total_values_p2 = self.total_values_p2 or self.total_values.clone().zero()
        torch.mul(self.total_values_p2, terminate_values, self.terminate_current_strategy)
        self.total_values.add(self.total_values_p2)

        self.play_current_regret = self.play_current_regret or play_values.clone().zero()
        self.terminate_current_regret = self.terminate_current_regret or self.play_current_regret.clone().zero()

        self.play_current_regret.copy(play_values)
        self.play_current_regret.csub(self.total_values)

        self.terminate_current_regret.copy(terminate_values)
        self.terminate_current_regret.csub(self.total_values)

        ##--1.1 cumulate regrets
        self.play_regrets.add(self.play_current_regret)
        self.terminate_regrets.add(self.terminate_current_regret)

        ##--2.0 we use cfr+ in reconstruction
        self.terminate_regrets.clamp(self.regret_epsilon, tools.max_number())
        self.play_regrets.clamp(self.regret_epsilon, tools.max_number())

        self.play_possitive_regrets = self.play_regrets
        self.terminate_possitive_regrets = self.terminate_regrets

        ##--3.0 regret matching
        self.regret_sum = self.regret_sum or self.play_possitive_regrets.clone().zero()
        self.regret_sum.copy(self.play_possitive_regrets)
        self.regret_sum.add(self.terminate_possitive_regrets)

        self.play_current_strategy.copy(self.play_possitive_regrets)
        self.terminate_current_strategy.copy(self.terminate_possitive_regrets)

        self.play_current_strategy.cdiv(self.regret_sum)
        self.terminate_current_strategy.cdiv(self.regret_sum)

        ##--4.0 for poker, the range size is larger than the allowed hands
        ##--we need to make sure reconstruction does not choose a range
        ##--that is not allowed
        self.play_current_strategy.cmul(self.range_mask)
        self.terminate_current_strategy.cmul(self.range_mask)

        self.input_opponent_range = self.input_opponent_range or self.play_current_strategy.clone().zero()
        self.input_opponent_range.copy(self.play_current_strategy)

        return self.input_opponent_range
