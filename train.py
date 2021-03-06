import util

total_time = util.start_timer()

import game
import lstm_ai
import ai as ai_module
import last_n_bodyparts_ai
import convnet_ai
import simple_ai

# import render

from matplotlib import pyplot

if util.use_cupy:
    import cupy as np
else:
    import numpy as np
    

import tensorflow as tf
from tensorflow.keras import backend as K

import math
import random
import datetime
import os

food_reward = 1

train_settings = [
#    "teacher",             # whether to learn from a teacher/supervised
    "reinforcement",        # whether to use reinforcement learning
#    "distance_food",       # whether to use the distance_food goal
    "probability_of_food",  # whether to use the probability_of_food goal
#    "dies",                 # whether to keep track of the agent dying the next step
    "probability_next_food",
    "cupy"
]

ai_module.train_settings = train_settings


if False:
    # use cpu
    print()
    print('using CPU!')
    print()
    tf.config.experimental.set_visible_devices([], 'GPU')

class Trainer:
    def __init__(self, ai, parallel_sessions):
        self.ai = ai
        self.train_data = [[] for i in range(parallel_sessions)]
        self.worlds_with_train_data = [(game.World(), self.train_data[i]) for i in range(parallel_sessions)]

    def step(self):
        start_timer = util.start_timer()
        """
        performs one simulation step and does necessary work for training
        """

        if "teacher" in train_settings:
            teacher_ai = ai_module.HardcodedAi(train_settings)
            teacher_move_indices = teacher_ai.predict_best_moves(
                [world for world, train_data in self.worlds_with_train_data]
            )

        # predict moves
        util.times_predicted += 1
        util.predicted_actions += len(self.worlds_with_train_data)
        move_indices = self.ai.predict_best_moves(
            [world for world, train_data in self.worlds_with_train_data]
        )

        removed_world_indices = []

        for i in range(len(self.worlds_with_train_data)):
            world, train_data = self.worlds_with_train_data[i]
            world.set_direction(game.directions[util.get_if_cupy(move_indices[i])])
            result = world.forward()

            learn_data = ai_module.LearnData(world, move_indices[i], 0)
            train_data.append(learn_data)

            if "distance_food" in train_settings:
                distance_food_x = abs(world.food[0] - world.snake[0][0])
                distance_food_y = abs(world.food[1] - world.snake[0][1])

                distance_food = distance_food_x + distance_food_y
                reward = 0.5 / distance_food if distance_food > 0 else 0.5
                reward = 1.5 * (0.8 ** distance_food)
            elif "reinforcement" in train_settings:
                reward = 0
            elif "teacher" in train_settings:
                reward = 1 if teacher_move_indices[i] == move_indices[i] else 0
                # train_data.append(ai_module.LearnData(world, move_indices[i], reward))
                learn_data.reward = reward
            
            reward = 0

            died = False
            if result == game.MoveResult.death:
                # stop world
                removed_world_indices.append(i)
                died = True

                if "reinforcement" in train_settings:
                    reward = -1
            elif result == game.MoveResult.eat:
                if "reinforcement" in train_settings:
                    reward = food_reward
                for data in train_data:
                    data.total_food += 1
                    if "probability_of_food" in train_settings and not "teacher" in train_settings:
                        data.reward = 1
            learn_data.died = died

            if "probability_of_food" in train_settings and not "teacher" in train_settings:
                # train_data.append(ai_module.LearnData(world, move_indices[i], 0))
                learn_data.reward = 0
            elif "reinforcement" in train_settings:
                
                gamma = 0.9
                reward_factor = 1

                if reward != 0:
                    for j in range(len(train_data) - 1, -1, -1):
                        train_data[j].reward += reward * reward_factor
                        reward_factor *= gamma
                
                # train_data.append(ai_module.LearnData(world, move_indices[i], reward))
                learn_data.reward = reward

        # remove the larger indices first
        removed_world_indices.sort(reverse=True)

        for index in removed_world_indices:
            del self.worlds_with_train_data[index]
        
        util.end_timer(start_timer, 'step')
    
    def simulate_entire_game(self):
        # counter = 0
        old_len = None
        while(len(self.worlds_with_train_data) > 0):
            # counter += 1

            # if counter > 200:
            #     for world, _ in self.worlds_with_train_data:
            #         renderer = render.Renderer(self.ai)
            #         renderer.world = world
            #         renderer.render_loop()
            #     return
            new_len = len(self.worlds_with_train_data)
            if verbosity >= 2 and old_len != new_len:
                print('step; worlds left =', new_len)
                old_len = new_len
            self.step()

    def train(self, epochs=1):
        # flatten train data, TODO: write something I understand myself
        flatten = lambda l: [item for sublist in l for item in sublist]
        flat_train_data = flatten(self.train_data)

        return self.ai.train(flat_train_data, epochs=epochs)

    def results(self):
        max_score = 0
        total_score = 0

        for datas in self.train_data:
            food_amount = datas[0].total_food

            if max_score < food_amount:
                max_score = food_amount

            total_score += food_amount

        return max_score, total_score
        

def train_supervised(teacher_ai, student_ai, rounds):
        trainer = Trainer(teacher_ai, rounds)
        trainer.simulate_entire_game()
        trainer.ai = student_ai
        trainer.train(3)


averages = []
losses = []
smoothed_averages = []

graphic_output_interval = 10
smooth_average_count = graphic_output_interval
pyplot.figure(0)

epochs = 5
simultaneous_worlds = 256
simulated_games_count = 0

switch_teacher_to_reinforcement = False

verbosity = 2
initialize_supervised = False
supervised_rounds = 5

best_average = 0
best_model = None


if __name__ == "__main__":
    # ai = simple_ai.SimpleAi()
    # ai = ai_module.HardcodedAi()
    # ai = convnet_ai.CenteredAI()
    # ai = last_n_bodyparts_ai.LastNBodyParts(2)
    # ai = last_n_bodyparts_ai.LastNBodyParts(3)
    # ai = convnet_ai.RotatedCenteredAI('models_output/2020-02-26 19:07-last.h5')
    # ai = convnet_ai.RotatedCenteredAI("models/RotatedCenteredAI_no_moving_backwards-last.h5")
    # ai = convnet_ai.RotatedCenteredAI('models_output/centered-rotated-ai-2020-03-18 14:26:59-above-6.h5')
    # ai = convnet_ai.RotatedCenteredAI('models_output/centered-rotated-ai-2020-03-18 13:45:42-above-6.h5')
    # ai = convnet_ai.RotatedCenteredAI('models_output/centered-rotated-ai-2020-03-20 09:52:24-above-12.h5')
    ai = convnet_ai.RotatedCenteredAI(train_settings)

    ai.epsilon = 0.05
    min_epsilon = 0.01
    epsilon_decrement_factor = 0.99

    # learning_rate = K.get_value(ai.model.optimizer.lr)
    learning_rate = 0.00001
    min_learning_rate = learning_rate * 0.1
    #learning_rate = min_learning_rate
    learning_rate_decrement_factor = 0.99
    ai.set_learning_rate(learning_rate)

    training_start = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_graph_name = None
    print('training_start =', training_start)

    done_output = 10

    if initialize_supervised:
        if verbosity >= 1:
            print('training supervised')
        for id in range(supervised_rounds):
            if verbosity >= 1:
                print("supervised round: ", id)
            
            old_verbosity = verbosity
            verbosity = min(verbosity, 1)
            train_supervised(ai_module.HardcodedAi(train_settings), ai, 1024 * 8)
            verbosity = old_verbosity

            if verbosity >= 2:
                print("trained supervised")
            
            if True and verbosity >= 1:
                trainer = Trainer(ai, 1024 * 2)
                trainer.simulate_entire_game()

                max_score, total_score = trainer.results()
                
                average = float(total_score) / len(trainer.train_data)

                print('max:', max_score, 'average', average)

        if False:
            renderer = render.Renderer(ai)
            renderer.render_loop()

    for epoch_id in range(1, epochs + 1):

        # ai.epsilon *= epsilon_decrement_factor
        # print("start epoch")
        if verbosity >= 1:
            print("starting epoch:", epoch_id)
        

        if epoch_id == 1:
            # performs some tests to make sure the GPU works
            name = tf.test.gpu_device_name()
            if name:
                print('Default GPU Device: {}'.format(name))
            else:
                print("not using gpu!")
            
            if tf.test.is_gpu_available():
                print("gpu available")
            else:
                print("no gpu available")


        if verbosity >= 2:
            print("creating trainer")
        trainer = Trainer(ai, simultaneous_worlds)
        
        if verbosity >= 2:
            print("simulating game")

        trainer.simulate_entire_game()

        if verbosity >= 2:
            print("get results")
        max_score, total_score = trainer.results()
        
        # `len(trainer.train_data)` is the amount of simulated worlds
        average = float(total_score) / len(trainer.train_data)

        if verbosity >= 2 or (initialize_supervised and verbosity == 1 and epoch_id == 1):
            print('max:', max_score, 'average', average)

        averages.append(average)
        if average > 1:
            ai.epsilon = max(ai.epsilon * epsilon_decrement_factor, min_epsilon)

            learning_rate = max(learning_rate * learning_rate_decrement_factor, min_learning_rate)
            ai.set_learning_rate(learning_rate)

        if average > best_average:
            best_average = average
            best_model = tf.keras.models.clone_model(ai.model)

        history = trainer.train()
        losses.append(history.history['loss'])

        if epoch_id % graphic_output_interval == 0:
            if verbosity >= 1:
                print('graphic output! Epoch:' + str(epoch_id))
            # ai.print_layer_weights()
            # output graph
            pyplot.style.use('default')
            pyplot.clf()
            pyplot.plot(averages, linewidth=0.5)

            for i in range(epoch_id - graphic_output_interval, epoch_id):
                start_index = max(0, i - smooth_average_count)
                smoothed_averages.append(sum(averages[start_index : i + 1]) / (i + 1 - start_index))

            pyplot.style.use('seaborn')
            pyplot.plot(smoothed_averages, linewidth=0.5)

            if verbosity == 1:
                print(str(smooth_average_count) + '-game average:', smoothed_averages[-1])

            if smoothed_averages[-1] > done_output:
                ai.save(training_start, '', '-above-' + str(done_output))
                done_output += 1

            if switch_teacher_to_reinforcement and smoothed_averages[-1] > 0.6 and "teacher" in train_settings:
                train_settings.remove("teacher")
                train_settings.append(["reinforcement"])
                if verbosity >= 1:
                    print() 
                    print("switching to reinforcement")
                    print()

            # new_graph_name = 'graph_output/graph-' + training_start + '-' + str(epoch_id).rjust(5, '0')
            new_graph_name = 'graph_output/graph-' + training_start
            pyplot.savefig(new_graph_name, dpi=300)

            # if last_graph_name != None:
            #     os.remove(last_graph_name + '.png')
            # last_graph_name = new_graph_name
        
            for _ in range(simulated_games_count):
                renderer = render.Renderer(ai)
                renderer.render_loop()


    ai.save(training_start, '', '-last')
    ai.model = best_model
    ai.save(training_start, '', '-best')

    if False:
        pyplot.figure(0)
        pyplot.plot(averages)
        last_update = epoch_id - (epoch_id % graphic_output_interval)

        for i in range(last_update, epoch_id):
            start_index = max(0, i - 10)
            smoothed_averages.append(sum(averages[start_index : i + 1]) / (i + 1 - start_index))

        pyplot.style.use('seaborn')
        pyplot.plot(smoothed_averages)

        pyplot.show()

    if False:
        import render

        for i in range(10):
            renderer = render.Renderer(ai)
        renderer.render_loop()

util.end_timer(total_time, 'total_time')

util.print_timers()